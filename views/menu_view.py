import asyncio

import flet as ft
import httpx

from models.platillo_dao import PlatilloDAO
from views.components.dialogo_platillo import DialogoPlatillo


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
        self.height = float("inf")
        self.bgcolor = "#fbf5e9"
        self.padding = ft.padding.only(left=36, right=36, top=42, bottom=36)

        # Lista maestra tal cual vino de Supabase (obtener_todos()) y la
        # versión actualmente pintada (tras aplicar el buscador) — se
        # necesitan las dos por separado: _platillos_mostrados es la que usa
        # el ojito para saber en qué índice de cuerpo_tabla.controls está
        # cada fila, sin tener que recargar toda la vista para un toggle.
        self._platillos: list[dict] = []
        self._platillos_mostrados: list[dict] = []
        self._banner_token = 0

        # Título grande: arranca en "cargando" y _mostrar_estado() lo
        # reemplaza por el conteo real (sigue al buscador) o por un título
        # neutro si hay error.
        self.texto_titulo = ft.Text(
            "Cargando tu menú...",
            size=40,
            font_family="Georgia",
            italic=True,
            color="#18120d",
        )

        self.campo_busqueda = ft.TextField(
            hint_text="Busca por nombre, categoría o ingrediente...",
            prefix_icon=ft.Icons.SEARCH,
            expand=True,
            height=52,
            border_radius=16,
            border_color="#eadfca",
            focused_border_color="#f4ca83",
            bgcolor="#f8f1de",
            color="#5e5449",
            hint_style=ft.TextStyle(color="#9b8f7e"),
            text_size=14,
            on_change=self._on_busqueda_change,
        )

        # Banner temporal para errores que no ocurren dentro de un diálogo
        # (hoy solo el ojito de visibilidad) — mismo estilo de caja de error
        # que sesion_view.py, con auto-ocultado igual que el toast de
        # EJEMPLOS/lilshop.html (mostrarMensaje/toastTimeoutId), adaptado a
        # asyncio.sleep en vez de setTimeout/clearTimeout.
        self.texto_banner_error = ft.Text("", size=12, color="#a33c39", expand=True)
        self.banner_error = ft.Container(
            visible=False,
            bgcolor="#f7e4e3",
            border=ft.border.all(1, "#d9534f"),
            border_radius=12,
            padding=ft.padding.symmetric(horizontal=12, vertical=10),
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE, size=15, color="#d9534f"),
                    self.texto_banner_error,
                ],
                spacing=8,
            ),
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
                                ft.Text("MI MENÚ", size=13, weight="bold", color="#b58a6d"),
                                self.texto_titulo,
                            ],
                        ),
                        ft.Container(
                            content=ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.ADD, color="#ffa200", size=22),
                                    ft.Text("Agregar platillo", color="#ffffff", weight="bold", size=16),
                                ],
                                spacing=8,
                            ),
                            bgcolor="#0d0905",
                            padding=ft.padding.symmetric(horizontal=26, vertical=16),
                            border_radius=30,
                            shadow=ft.BoxShadow(
                                blur_radius=12,
                                color=ft.Colors.with_opacity(0.28, ft.Colors.BLACK),
                                offset=ft.Offset(0, 4),
                            ),
                            ink=True,
                            on_click=self._on_agregar_click,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(height=18),
                self.banner_error,
                ft.Container(height=18),
                self.campo_busqueda,
                ft.Container(height=20),
                ft.Container(
                    bgcolor="#eee5cf",
                    border_radius=14,
                    padding=ft.padding.symmetric(horizontal=18, vertical=14),
                    content=ft.Row(
                        controls=[
                            self._header("PLATILLO", 3),
                            self._header("DESCRIPCIÓN", 2),
                            self._header("CATEGORÍA", 1),
                            self._header("PRECIO", 1),
                            self._header("VISIBILIDAD", 1),
                            ft.Container(width=108),
                        ],
                        spacing=12,
                    ),
                ),
                self.cuerpo_tabla,
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
        return ft.Text(
            texto,
            size=11,
            weight="bold",
            color="#806f61",
            expand=expand,
        )

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

    def _estado_cargando(self):
        return [
            ft.Container(
                bgcolor="#f8f1de",
                border_radius=14,
                padding=ft.padding.symmetric(vertical=48),
                alignment=ft.Alignment(0, 0),
                content=ft.Column(
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                    controls=[
                        ft.ProgressRing(width=28, height=28, stroke_width=3, color="#f4ca83"),
                        ft.Text("Cargando tu menú...", size=13, color="#7c7267"),
                    ],
                ),
            )
        ]

    def _estado_vacio(self):
        return [
            ft.Container(
                bgcolor="#f8f1de",
                border_radius=14,
                padding=ft.padding.symmetric(vertical=48),
                alignment=ft.Alignment(0, 0),
                content=ft.Column(
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                    controls=[
                        ft.Icon(ft.Icons.RESTAURANT_MENU_OUTLINED, size=30, color="#c9bda3"),
                        ft.Text(
                            "Todavía no hay platillos en el menú.",
                            size=14,
                            weight="bold",
                            color="#5e5449",
                        ),
                        ft.Text(
                            "Agrega el primero con el botón de arriba.",
                            size=12,
                            color="#8a7e72",
                        ),
                    ],
                ),
            )
        ]

    def _estado_sin_resultados(self, query: str):
        """Estado vacío distinto al de "menú vacío" — el menú SÍ tiene
        platillos, solo que ninguno coincide con lo que se buscó."""
        return [
            ft.Container(
                bgcolor="#f8f1de",
                border_radius=14,
                padding=ft.padding.symmetric(vertical=48),
                alignment=ft.Alignment(0, 0),
                content=ft.Column(
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                    controls=[
                        ft.Icon(ft.Icons.SEARCH_OFF, size=30, color="#c9bda3"),
                        ft.Text(
                            f'No encontramos platillos para "{query}".',
                            size=14,
                            weight="bold",
                            color="#5e5449",
                        ),
                        ft.Text(
                            "Prueba con otro nombre, categoría o palabra clave.",
                            size=12,
                            color="#8a7e72",
                        ),
                    ],
                ),
            )
        ]

    def _estado_error(self):
        # Mismo estilo de error que views/sesion_view.py (zona_error): fondo
        # rojo aguado, borde y texto rojo, ícono de alerta — es el lenguaje
        # visual de error que ya quedó definido para todo el proyecto.
        return [
            ft.Container(
                bgcolor="#f7e4e3",
                border=ft.border.all(1, "#d9534f"),
                border_radius=12,
                padding=ft.padding.symmetric(horizontal=12, vertical=10),
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.ERROR_OUTLINE, size=15, color="#d9534f"),
                        ft.Text(
                            "No hay conexión con el servidor. Revisa tu internet.",
                            size=12,
                            color="#a33c39",
                            expand=True,
                        ),
                    ],
                    spacing=8,
                ),
            )
        ]

    # ------------------------------------------------------------------
    # Filas y sus acciones (ojito / lápiz / "…")
    # ------------------------------------------------------------------
    def _crear_fila(self, platillo: dict):
        nombre = platillo.get("nombre") or ""
        descripcion = platillo.get("descripcion") or ""
        categoria = platillo.get("categoria") or ""
        precio = _formatear_precio(platillo.get("precio"))
        visible = bool(platillo.get("visible", True))
        imagen = platillo.get("image_url") or "assets/taco.jpg"

        return ft.Container(
            bgcolor="#f8f1de",
            padding=ft.padding.symmetric(horizontal=18, vertical=12),
            border=ft.border.only(bottom=ft.BorderSide(1, "#eadfca")),
            content=ft.Row(
                controls=[
                    ft.Row(
                        expand=3,
                        spacing=12,
                        controls=[
                            ft.Image(
                                src=imagen,
                                width=38,
                                height=38,
                                fit=ft.BoxFit.COVER,
                                border_radius=8,
                            ),
                            ft.Text(
                                nombre,
                                size=15,
                                font_family="Georgia",
                                italic=True,
                                weight="bold",
                                color="#1c1610",
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Text(descripcion, size=12, color="#5e5449", expand=2),
                    ft.Container(
                        expand=1,
                        alignment=ft.Alignment(-1, 0),
                        content=ft.Container(
                            # Sin width fijo (antes width=58): "Platillos" no
                            # cabía. Sin width, el chip se ajusta solo al
                            # texto — único ajuste de layout que pidió la Fase 2.
                            content=ft.Text(categoria, size=10, weight="bold", color="#684c16"),
                            bgcolor="#f7b84d",
                            padding=ft.padding.symmetric(horizontal=9, vertical=4),
                            border_radius=12,
                        ),
                    ),
                    ft.Text(precio, size=13, weight="bold", color="#1c1610", expand=1),
                    ft.Container(
                        expand=1,
                        alignment=ft.Alignment(-1, 0),
                        content=self._badge_visibilidad(visible),
                    ),
                    ft.Row(
                        controls=[
                            self._accion(
                                ft.Icons.VISIBILITY_OFF_OUTLINED,
                                on_click=lambda e, p=platillo: self._on_toggle_visibilidad(p),
                                tooltip="Ocultar del menú público" if visible else "Mostrar en el menú público",
                            ),
                            self._accion(
                                ft.Icons.EDIT_OUTLINED,
                                on_click=lambda e, p=platillo: self._on_editar_click(p),
                                tooltip="Editar platillo",
                            ),
                            # Apartado a propósito (ver roadmap, Fase 2.6):
                            # va a mostrar cuántas veces se vendió este
                            # platillo cuando existan ventas + mesas (Fases
                            # 5 y 6). Se queda inerte, sin ícono ni
                            # comportamiento nuevo.
                            self._accion(ft.Icons.MORE_HORIZ),
                        ],
                        spacing=4,
                        width=108,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def _badge_visibilidad(self, visible: bool):
        """Mismo formato (borde + puntito + texto) para los dos estados;
        oculto = false lo pinta en rojo #d9534f diciendo OCULTO. La fila
        sigue en la tabla — nunca se borra, solo deja de salir en el
        menú público."""
        if visible:
            color_punto, color_texto, color_borde, texto = "#7d8545", "#6e704c", "#c9c5a8", "VISIBLE"
        else:
            color_punto, color_texto, color_borde, texto = "#d9534f", "#a33c39", "#d9534f", "OCULTO"

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(width=7, height=7, bgcolor=color_punto, border_radius=4),
                    ft.Text(texto, size=10, weight="bold", color=color_texto),
                ],
                spacing=5,
            ),
            border=ft.border.all(1, color_borde),
            border_radius=12,
            width=80,
            padding=ft.padding.symmetric(horizontal=8, vertical=4),
        )

    def _accion(self, icono: str, on_click=None, tooltip: str = None):
        return ft.Container(
            content=ft.Icon(icono, size=16, color="#756b5e"),
            width=30,
            height=30,
            alignment=ft.Alignment(0, 0),
            border_radius=15,
            ink=True,
            on_click=on_click,
            tooltip=tooltip,
        )

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

    def _mostrar_error_temporal(self, mensaje: str, duracion_seg: int = 4):
        """Toast de error para acciones que ocurren directo en la tabla (el
        ojito), sin un diálogo propio donde pintar la caja de error. Mismo
        patrón que mostrarMensaje()/toastTimeoutId de EJEMPLOS/lilshop.html,
        adaptado a asyncio.sleep en vez de setTimeout/clearTimeout."""
        self._banner_token += 1
        token = self._banner_token
        self.texto_banner_error.value = mensaje
        self.banner_error.visible = True
        self.banner_error.update()
        self.router.page.run_task(self._ocultar_banner_luego, token, duracion_seg)

    async def _ocultar_banner_luego(self, token: int, duracion_seg: int):
        await asyncio.sleep(duracion_seg)
        if token != self._banner_token:
            return  # ya llegó un mensaje más nuevo, no lo tapes
        self.banner_error.visible = False
        self.banner_error.update()

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

    def _on_guardado(self):
        """Se llama tras crear/actualizar/eliminar con éxito desde el
        diálogo. A diferencia del ojito, aquí SÍ se recarga la tabla contra
        Supabase de verdad — un alta cambia el total y el orden, una edición
        puede cambiar cualquier columna visible, y un borrado quita la fila
        por completo; no alcanza con parchar una sola fila en memoria.

        NOTA para la Fase 4: cuando exista el menú público, aquí también
        habrá que invalidar su caché (igual que invalidarCacheCatalogo() en
        EJEMPLOS/lilshop.html) — todavía no aplica, ese menú no existe."""
        self.router.page.run_task(self._cargar_platillos)
