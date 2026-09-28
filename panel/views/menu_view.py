import asyncio

import flet as ft
import httpx

from models.platillo_dao import PlatilloDAO
from views.components.dialogo_platillo import DialogoPlatillo
from views.piezas import (aviso, boton_atajo, boton_icono, campo, fondo_pagina, pastilla,
                          pildora_estado, tarjeta_iphone, texto, titulo_vista)
from views.tema import C


def _texto_contador(cantidad: int) -> str:
    """'1 platillo en la mesa' vs '4 platillos en la mesa' — cuida el singular."""
    if cantidad == 1:
        return "1 platillo en la mesa"
    return f"{cantidad} platillos en la mesa"


def _formatear_precio(valor) -> str:
    """precio llega como numeric(10,2) de Supabase (float en Python). Los
    platillos de prueba son todos enteros ($300, $150...) así que se pintan
    sin decimales para verse igual que antes; si algún día hay centavos de
    verdad, se muestran."""
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return "$0"
    if numero.is_integer():
        return f"${int(numero):,}"
    return f"${numero:,.2f}"


def _coincide(platillo: dict, query: str) -> bool:
    """Buscador de la Fase 2.6: compara contra nombre, descripción y
    categoría, sin distinguir mayúsculas/acentos exactos (substring simple,
    que es lo que pide el buscador para 10-20 platillos)."""
    campos = (
        platillo.get("nombre") or "",
        platillo.get("descripcion") or "",
        platillo.get("categoria") or "",
    )
    return any(query in campo.lower() for campo in campos)


class MenuView(ft.Container):
    def __init__(self, router, abrir_dialogo_nuevo: bool = False):
        super().__init__()
        self.router = router
        self.expand = True
        self.bgcolor = C.fondo
        self.gradient = fondo_pagina()
        self.padding = 40

        # Lista maestra tal cual vino de Supabase (obtener_todos()) y la
        # versión actualmente pintada (tras aplicar el buscador) — se
        # necesitan las dos por separado: _platillos_mostrados es la que usa
        # el ojito para saber en qué índice de cuerpo_tabla.controls está
        # cada fila, sin tener que recargar toda la vista para un toggle.
        self._platillos: list[dict] = []
        self._platillos_mostrados: list[dict] = []

        # Título grande: arranca en "cargando" y _mostrar_estado() lo
        # reemplaza por el conteo real (sigue al buscador) o por un título
        # neutro si hay error.
        self.texto_titulo = titulo_vista("Cargando tu menú...")

        self.campo_busqueda = campo(
            pista="Busca por nombre, categoría o ingrediente...",
            icono=ft.Icons.SEARCH,
            tamano=13,
            al_cambiar=self._on_busqueda_change,
        )

        # Cuerpo de la tabla: arranca mostrando el estado de "cargando" y se
        # reemplaza por las filas reales (o por vacío/sin-resultados/error)
        # cuando _cargar_platillos()/_aplicar_filtro() corren.
        self.cuerpo_tabla = ft.Column(
            spacing=0,
            controls=self._estado_cargando(),
        )

        self.content = ft.Column(
            expand=True,
            height=float("inf"),
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.Row(
                    controls=[
                        ft.Column(
                            expand=True,
                            spacing=2,
                            controls=[
                                texto("MI MENÚ", 14),
                                self.texto_titulo,
                            ],
                        ),
                        boton_atajo(ft.Icons.ADD, "Agregar platillo", self._on_agregar_click,
                                    ancho=200),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(height=25),
                ft.Row([self.campo_busqueda]),
                ft.Container(height=10),
                # La tabla va dentro de una tarjeta: títulos de columna, raya y filas.
                tarjeta_iphone(ft.Column([
                    ft.Row(
                        controls=[
                            self._header("PLATILLO", 3),
                            self._header("DESCRIPCIÓN", 2),
                            self._header("CATEGORÍA", 1),
                            self._header("PRECIO", 1),
                            self._header("VISIBILIDAD", 1),
                            ft.Container(width=124),
                        ],
                        spacing=14,
                    ),
                    ft.Container(height=10),
                    ft.Divider(height=1, thickness=1, color=C.linea),
                    self.cuerpo_tabla,
                ], spacing=0), expand=None),
            ],
        )

        # Dispara la carga real apenas se monta la vista. Se agenda aquí
        # (todavía dentro de __init__, síncrono) pero no arranca de verdad
        # hasta que el event loop recupera el control — es decir, después de
        # que cambiar_vista() termine de montar esta vista y llame a
        # page.update(). Mismo patrón que _maximizar_ventana en
        # main_controller.py.
        self.router.page.run_task(self._cargar_platillos)

        # Fase 2.7: si se llegó aquí desde el atajo "Agregar un producto
        # nuevo" de home_view.py, abre el diálogo de alta apenas esta vista
        # queda montada — mismo truco de run_task que la línea de arriba
        # (no corre de verdad hasta que cambiar_vista() termine y llame a
        # page.update()), así el diálogo se abre sobre la vista ya en
        # pantalla, no sobre una todavía a medio construir.
        if abrir_dialogo_nuevo:
            self.router.page.run_task(self._abrir_dialogo_nuevo_al_montar)

    def _header(self, texto: str, expand: int):
        return ft.Text(texto, size=12, color=C.texto_suave, font_family="LetraTexto", expand=expand)

    # ------------------------------------------------------------------
    # Carga y buscador
    # ------------------------------------------------------------------
    async def _cargar_platillos(self):
        try:
            # obtener_todos() es una llamada de red bloqueante (supabase-py
            # es síncrono) — se manda a un hilo aparte para no congelar la
            # ventana, igual que sign_in_with_password en sesion_view.py.
            self._platillos = await asyncio.to_thread(PlatilloDAO.obtener_todos)
        except httpx.RequestError as e:
            print(f"[menu] error de red al traer platillos: {e}")
            self._platillos = []
            self._mostrar_estado(self._estado_error(), "Tu menú")
            return
        except Exception as e:
            print(f"[menu] error inesperado al traer platillos: {e}")
            self._platillos = []
            self._mostrar_estado(self._estado_error(), "Tu menú")
            return

        self._aplicar_filtro()

    def _on_busqueda_change(self, e):
        # Filtra en el cliente sobre self._platillos, que ya está cargado —
        # NO vuelve a pegarle a Supabase en cada tecla.
        self._aplicar_filtro()

    def _aplicar_filtro(self):
        query = (self.campo_busqueda.value or "").strip().lower()
        filtrados = (
            [p for p in self._platillos if _coincide(p, query)]
            if query
            else list(self._platillos)
        )
        self._platillos_mostrados = filtrados

        if not self._platillos:
            # El menú está realmente vacío (no es cosa del buscador).
            self._mostrar_estado(self._estado_vacio(), _texto_contador(0))
        elif not filtrados:
            # Hay platillos, pero ninguno coincide con la búsqueda —
            # mensaje distinto al de "menú vacío", como pidió el dueño.
            self._mostrar_estado(self._estado_sin_resultados(query), _texto_contador(0))
        else:
            filas = [self._crear_fila(p) for p in filtrados]
            self._mostrar_estado(filas, _texto_contador(len(filtrados)))

    def _mostrar_estado(self, controles: list, texto_titulo: str):
        self.cuerpo_tabla.controls = controles
        self.texto_titulo.value = texto_titulo
        self.cuerpo_tabla.update()
        self.texto_titulo.update()

    def _nota(self, *lineas):
        # Los estados de la tabla (cargando, vacía, sin resultados, sin conexión): una nota
        # dentro de la propia tarjeta, sin rueda de carga ni cajas rojas.
        return [
            ft.Container(
                padding=ft.Padding.symmetric(vertical=40),
                alignment=ft.Alignment(0, 0),
                content=ft.Column(
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=6,
                    controls=[texto(lineas[0], 14)] + [texto(l, 12, suave=True) for l in lineas[1:]],
                ),
            )
        ]

    def _estado_cargando(self):
        return self._nota("Cargando tu menú...", "Un momento…")

    def _estado_vacio(self):
        return self._nota("Todavía no hay platillos en el menú.",
                          "Agrega el primero con el botón de arriba.")

    def _estado_sin_resultados(self, query: str):
        """Distinto al de "menú vacío": el menú SÍ tiene platillos, solo que ninguno
        coincide con lo que se buscó."""
        return self._nota(f'No encontramos platillos para "{query}".',
                          "Prueba con otro nombre, categoría o palabra clave.")

    def _estado_error(self):
        return self._nota("Sin conexión.", "No hay conexión con el servidor. Revisa tu internet.")

    # ------------------------------------------------------------------
    # Filas y sus acciones (ojito / lápiz / "…")
    # ------------------------------------------------------------------
    def _crear_fila(self, platillo: dict):
        nombre = platillo.get("nombre") or ""
        descripcion = platillo.get("descripcion") or ""
        categoria = platillo.get("categoria") or ""
        precio = _formatear_precio(platillo.get("precio"))
        visible = bool(platillo.get("visible", True))
        imagen = platillo.get("image_url") or "assets/sin-foto.png"

        foto = ft.Image(
            src=imagen,
            width=48,
            height=48,
            fit=ft.BoxFit.COVER,
            border_radius=6,
            cache_width=144,
            # Si la foto de R2 no carga (URL rota, sin internet), el mismo placeholder que las
            # filas sin foto en vez de un ícono roto.
            error_content=ft.Image(src="assets/sin-foto.png", width=48, height=48,
                                   fit=ft.BoxFit.COVER, border_radius=6),
            # Lo oculto va al 40 % (sin rojo).
            opacity=1 if visible else 0.4,
        )

        return ft.Container(
            height=70,
            border=ft.Border.only(bottom=ft.BorderSide(1, C.linea)),
            content=ft.Row(
                controls=[
                    ft.Row(
                        expand=3,
                        spacing=12,
                        controls=[
                            foto,
                            texto(nombre, 14, titulo=True, expand=True, max_lines=2,
                                  overflow=ft.TextOverflow.ELLIPSIS),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    texto(descripcion, 12, suave=True, expand=2, max_lines=2,
                          overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Container(expand=1, alignment=ft.Alignment(-1, 0), content=pastilla(categoria)),
                    texto(precio, 14, expand=1),
                    ft.Container(
                        expand=1,
                        alignment=ft.Alignment(-1, 0),
                        content=self._badge_visibilidad(visible),
                    ),
                    ft.Row(
                        controls=[
                            boton_icono(
                                ft.Icons.VISIBILITY_OFF_OUTLINED,
                                lambda e, p=platillo: self._on_toggle_visibilidad(p),
                                "Ocultar del menú público" if visible else "Mostrar en el menú público",
                            ),
                            boton_icono(
                                ft.Icons.EDIT_OUTLINED,
                                lambda e, p=platillo: self._on_editar_click(p),
                                "Editar platillo",
                            ),
                            # Apartado a propósito (roadmap, Fase 2.6): inerte.
                            boton_icono(ft.Icons.MORE_HORIZ),
                        ],
                        spacing=8,
                        width=124,
                    ),
                ],
                spacing=14,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def _badge_visibilidad(self, visible: bool):
        """VISIBLE / OCULTO con la píldora de estado sin color. La fila sigue en la tabla:
        ocultar nunca borra, solo deja de salir en el menú público."""
        return pildora_estado("VISIBLE" if visible else "OCULTO", encendida=visible)

    # ------------------------------------------------------------------
    # Ojito: cambiar visibilidad sin recargar toda la tabla
    # ------------------------------------------------------------------
    def _on_toggle_visibilidad(self, platillo: dict):
        self.router.page.run_task(self._alternar_visibilidad, platillo)

    async def _alternar_visibilidad(self, platillo: dict):
        nuevo_valor = not bool(platillo.get("visible", True))
        try:
            actualizado = await asyncio.to_thread(
                PlatilloDAO.cambiar_visibilidad, platillo["id"], nuevo_valor
            )
        except httpx.RequestError as e:
            print(f"[menu] error de red al cambiar visibilidad: {e}")
            self._mostrar_error_temporal(
                "No hay conexión con el servidor. Revisa tu internet."
            )
            return
        except Exception as e:
            print(f"[menu] error al cambiar visibilidad: {e}")
            self._mostrar_error_temporal(
                "No se pudo actualizar la visibilidad. Intenta de nuevo."
            )
            return

        # Ocultar NO borra: la fila se queda en Supabase y en la tabla del
        # panel, solo deja de salir en el menú público. Aquí solo se refleja
        # el nuevo valor en memoria y se repinta ÚNICAMENTE esa fila — no se
        # vuelve a consultar Supabase ni se reconstruye toda la tabla.
        valor_final = bool(actualizado.get("visible", nuevo_valor))
        for lista in (self._platillos, self._platillos_mostrados):
            for p in lista:
                if p.get("id") == platillo.get("id"):
                    p["visible"] = valor_final
        self._refrescar_fila(platillo["id"])

    def _refrescar_fila(self, id_platillo):
        for indice, p in enumerate(self._platillos_mostrados):
            if p.get("id") == id_platillo and indice < len(self.cuerpo_tabla.controls):
                self.cuerpo_tabla.controls[indice] = self._crear_fila(p)
                self.cuerpo_tabla.update()
                return

    def _mostrar_error_temporal(self, mensaje: str):
        """Avisos de lo que pasa directo en la tabla (el ojito, la limpieza de una foto): la
        píldora de aviso del panel, abajo."""
        aviso(self.router.page, mensaje)

    # ------------------------------------------------------------------
    # Agregar / editar: abren el mismo diálogo (Fase 2.6)
    # ------------------------------------------------------------------
    def _on_agregar_click(self, e):
        DialogoPlatillo(self.router, on_guardado=self._on_guardado, platillo=None).abrir()

    async def _abrir_dialogo_nuevo_al_montar(self):
        """Ver el run_task en __init__: existe solo para diferir la apertura
        del diálogo hasta que el event loop recupera el control, igual que
        _cargar_platillos."""
        self._on_agregar_click(None)

    def _on_editar_click(self, platillo: dict):
        DialogoPlatillo(self.router, on_guardado=self._on_guardado, platillo=platillo).abrir()

    def _on_guardado(self, aviso_limpieza: str | None = None):
        """Se llama tras crear/actualizar/eliminar con éxito desde el
        diálogo. A diferencia del ojito, aquí SÍ se recarga la tabla contra
        Supabase de verdad — un alta cambia el total y el orden, una edición
        puede cambiar cualquier columna visible, y un borrado quita la fila
        por completo; no alcanza con parchar una sola fila en memoria.

        `aviso_limpieza` (Fase 3): el guardado/borrado en Supabase YA salió
        bien cuando esto se llama, pero dialogo_platillo.py puede mandar un
        mensaje si de pasada falló borrar una foto vieja/huérfana en
        Cloudflare R2 (ver models/cloudflare_storage.py — ese fallo ya
        quedó registrado en huerfanos_r2.json de todos modos, esto es solo
        para que el dueño se entere en el momento). Se reusa el mismo
        banner rojo temporal del ojito porque el proyecto no tiene un
        segundo lenguaje visual de "aviso" — el texto ya aclara que la
        acción principal sí se completó.

        NOTA para la Fase 4: cuando exista el menú público, aquí también
        habrá que invalidar su caché (igual que invalidarCacheCatalogo() en
        EJEMPLOS/lilshop.html) — todavía no aplica, ese menú no existe."""
        if aviso_limpieza:
            self._mostrar_error_temporal(aviso_limpieza)
        self.router.page.run_task(self._cargar_platillos)
