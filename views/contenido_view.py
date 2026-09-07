"""
views/contenido_view.py
Fase 7.3 — el asistente real de creación de contenido. Conecta el catálogo
de plantillas (models/plantillas.py, Fase 7.1) y el compositor Pillow
(models/generador_anuncios.py, Fase 7.2) al lenguaje visual que YA estaba
aprobado en el wizard estático de la 7.0-7.2: los pills de paso con check
verde, la tarjeta #f8f1de con sombra, las miniaturas 176x198 con anillo de
selección, y el botón negro con AUTO_AWESOME. No se rediseñó nada — donde
algo no tenía con qué mapearse en el diseño existente se documenta abajo
en vez de improvisarse en silencio.

MAPEO DE PASOS (decisión explícita, pedida así por el dueño en el prompt de
esta fase, no asumida)
-----------------------------------------------------------------------
El wizard estático pintaba 3 pasos: "Elegir tipo de anuncio" / "Elegir
platillo" / "Instrucciones". El flujo real que pidió el dueño (roadmap,
"EL FLUJO QUE PIDIÓ EL DUEÑO") tiene 4 decisiones con datos completamente
distintos entre sí — diseño, platillo, texto, formato — más un resultado
que ya queda guardado solo. Meter texto Y formato dentro de un único paso
"Instrucciones" habría escondido dos pantallas distintas (un formulario de
texto que cambia de forma según la plantilla, y un selector de dos
tamaños de salida) detrás de una sola etiqueta. Se optó por CRECER la fila
de pasos a 4 pills, uno por decisión real: Diseño / Platillo / Texto /
Formato — mismo componente visual (_paso), generalizado para N pasos en
vez de 3 fijos.

La "vista previa -> guardado" (paso 6 del roadmap) NO es un 5to pill:
generador_anuncios.generar_anuncio() ya escribe el archivo en biblioteca/
al componerlo (ver su docstring — "generar y guardar son el mismo acto"),
así que no hay una acción de "guardar" independiente que merezca su propio
paso. Se resuelve como una pantalla de resultado dentro de la misma
tarjeta, con los 4 pills ya en verde — es la respuesta del asistente a
"ya terminaste", no un paso más que completar.

Las "pestañas" (Continuo/Comida rápida) del wizard estático tampoco tenían
con qué mapearse tal cual: obtener_plantillas() regresa 4 plantillas
PLANAS, sin ninguna agrupación de "estilos" en el catálogo real. En vez de
inventar una categoría que no existe en los datos, se reaprovechó el
MISMO componente (el pill _pestana ya aprobado) para lo que sí tiene
exactamente dos opciones reales: elegir FORMATO (post/historia) en el
paso 4 — mismo control visual, datos reales en vez de inventados.

ESTADO DEL ASISTENTE
---------------------
Un único diccionario de instancia por campo (no un dataclass aparte): se
conserva completo mientras el dueño navega hacia atrás y adelante entre
pasos (clic en un pill ya completado), así que volver a "Diseño" y luego
seguir de nuevo no borra el platillo/texto/formato ya elegidos. La única
limpieza deliberada es _textos al cambiar de plantilla (los campos son
específicos de cada plantilla — headline_stack no es headline) y el reseteo
completo al pedir "Crear otro anuncio" desde la pantalla de resultado.

Selección por clic (diseño/platillo/formato) deshabilita+atenúa el botón
"Continuar" cuando no hay nada elegido (no se puede fallar validando algo
que ya es imposible de dejar vacío). El paso de TEXTO es lo único que
valida al hacer clic en "Continuar", con el mismo banner rojo
#f7e4e3/#d9534f/#a33c39 que ya usa dialogo_platillo.py/menu_view.py — un
TextField no se puede "apagar" de forma útil mientras se escribe, así que
aquí se seguyó el mismo patrón que _validar() en dialogo_platillo.py en
vez de inventar un tercer lenguaje de validación.

generar_anuncio() es bloqueante (Pillow + una descarga a R2) — se llama
con asyncio.to_thread, mismo convenio que el resto del proyecto; mientras
corre, el botón muestra el mismo ProgressRing dorado que ya usa
dialogo_platillo.py (nunca el logo animado de "Pensando..." — ese es
exclusivo de agenteIA_view.py, ver CLAUDE.md). Un fallo (sin internet, un
ValueError de validación de generar_anuncio) se muestra con el banner rojo
compartido, nunca con un try/except mudo.
"""
import asyncio
import traceback

import flet as ft
import httpx

from models.generador_anuncios import generar_anuncio
from models.plantillas import FORMATOS, obtener_plantilla, obtener_plantillas
from models.platillo_dao import PlatilloDAO

# Etiquetas de los campos de texto que puede pedir una plantilla (ver
# Formato.campos_texto en models/plantillas.py, trampa #6 del roadmap):
# (etiqueta corta, hint de ejemplo, ícono). headline_stack lleva su propia
# aclaración aparte en _pantalla_texto() porque, a diferencia de los otros
# dos, el dueño lo escribe UNA sola vez y generador_anuncios.py lo repite
# solo — eso no es obvio con solo un hint.
_CAMPOS_TEXTO = {
    "headline": ("Título principal", "Ej. TACO ÁRABE", ft.Icons.TITLE),
    "subline": ("Subtítulo", "Ej. SABOR CASERO Y DELICIOSO", ft.Icons.SHORT_TEXT),
    "headline_stack": ("Frase", "Ej. SABOR AUTÉNTICO", ft.Icons.REPEAT),
}

_ETIQUETAS_PASOS = [(1, "Diseño"), (2, "Platillo"), (3, "Texto"), (4, "Formato")]

_SUBTITULOS = {
    1: "Elige un estilo para comenzar tu próxima publicación.",
    2: "Elige el platillo que quieres promocionar.",
    3: "Escribe el texto que llevará tu anuncio.",
    4: "Elige en qué formato quieres publicarlo.",
}


class ContenidoView(ft.Container):
    def __init__(self, router):
        super().__init__()
        self.router = router
        self.expand = True
        self.height = float("inf")
        self.bgcolor = "#fbf5e9"
        self.padding = ft.padding.only(left=36, right=36, top=42, bottom=36)

        # El catálogo de plantillas ya está en memoria desde que se
        # importó models/plantillas.py (Fase 7.1, se lee UNA vez al
        # importar el módulo) — no hay red ni Pillow de por medio todavía,
        # así que se puede leer directo aquí en __init__.
        self._plantillas = obtener_plantillas()

        # ---------------- estado del asistente ----------------
        self._paso_actual = 1
        self._mostrando_resultado = False
        self._plantilla_id: str | None = None
        self._platillo_id: int | None = None
        self._platillo_seleccionado: dict | None = None
        self._textos: dict[str, str] = {}
        self._campos_texto_controles: dict[str, ft.TextField] = {}
        self._formato_id: str | None = None
        self._ruta_generada: str | None = None
        self._generando = False

        # Paso 2 — la lista se carga de forma PEREZOSA la primera vez que
        # se entra a ese paso (ver _pantalla_platillo), no aquí en
        # __init__: es una llamada de red y no toda visita a "Crear
        # contenido" llega hasta ese paso.
        self._platillos_con_recorte: list[dict] | None = None
        self._cargando_platillos = False
        self._error_platillos = False

        # ---------------- banner de error compartido ----------------
        # Mismo lenguaje visual que menu_view.py/dialogo_platillo.py. A
        # diferencia del banner TEMPORAL de menu_view.py (se autooculta:
        # avisa de algo que ya pasó y el guardado principal ya salió
        # bien), este se queda visible hasta que el dueño lo resuelve o
        # avanza — es un bloqueo real para seguir en el asistente (texto
        # incompleto, sin conexión al generar), no un aviso de cortesía.
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

        self.texto_subtitulo = ft.Text(_SUBTITULOS[1], size=15, color="#7c7267")
        self.fila_pasos = ft.Row(
            controls=self._construir_pasos(),
            spacing=14,
            wrap=True,
            run_spacing=10,
            alignment=ft.MainAxisAlignment.START,
        )
        self.tarjeta = ft.Container(
            bgcolor="#f8f1de",
            border_radius=24,
            padding=ft.padding.only(left=28, right=28, top=26, bottom=24),
            shadow=ft.BoxShadow(
                blur_radius=22,
                spread_radius=1,
                color=ft.Colors.with_opacity(0.22, "#030303"),
                offset=ft.Offset(0, 7),
            ),
            content=self._construir_paso(),
        )

        self.content = ft.Column(
            expand=True,
            height=float("inf"),
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.Text("CREAR CONTENIDO", size=13, weight="bold", color="#b58a6d"),
                ft.Text(
                    "Hagamos algo bonito para Instagram",
                    size=42,
                    font_family="Georgia",
                    italic=True,
                    color="#18120d",
                ),
                self.texto_subtitulo,
                ft.Container(height=24),
                self.fila_pasos,
                ft.Container(height=24),
                self.banner_error,
                ft.Container(height=18),
                self.tarjeta,
            ],
        )

    # ------------------------------------------------------------------
    # Repintado
    # ------------------------------------------------------------------
    def _actualizar_seguro(self, *controles):
        """Igual que _refrescar() en agenteIA_view.py: si el dueño navegó
        a otra pantalla mientras una carga/generación seguía en vuelo, esta
        vista ya está desmontada y .update() lanzaría una excepción que no
        vería nadie — se traga a propósito en vez de tumbar la tarea."""
        for control in controles:
            try:
                control.update()
            except Exception:
                pass

    def _construir_pasos(self):
        return [self._paso(numero, texto) for numero, texto in _ETIQUETAS_PASOS]

    def _construir_paso(self):
        if self._mostrando_resultado:
            return self._pantalla_resultado()
        if self._paso_actual == 1:
            return self._pantalla_diseno()
        if self._paso_actual == 2:
            return self._pantalla_platillo()
        if self._paso_actual == 3:
            return self._pantalla_texto()
        return self._pantalla_formato()

    def _repintar(self):
        """Repinta pills + tarjeta + subtítulo — para cambios de PASO."""
        self.fila_pasos.controls = self._construir_pasos()
        self.tarjeta.content = self._construir_paso()
        self.texto_subtitulo.value = (
            "Tu anuncio ya está listo." if self._mostrando_resultado
            else _SUBTITULOS.get(self._paso_actual, "")
        )
        self._actualizar_seguro(self.fila_pasos, self.tarjeta, self.texto_subtitulo)

    def _repintar_tarjeta(self):
        """Repinta solo la tarjeta — para cambios DENTRO del mismo paso
        (elegir una plantilla/platillo/formato, o el estado de carga del
        paso 2), sin tocar los pills ni el subtítulo."""
        self.tarjeta.content = self._construir_paso()
        self._actualizar_seguro(self.tarjeta)

    def _ir_a(self, numero: int):
        self._paso_actual = numero
        self._ocultar_banner()
        self._repintar()

    def _mostrar_banner(self, mensaje: str):
        self.texto_banner_error.value = mensaje
        self.banner_error.visible = True
        self._actualizar_seguro(self.banner_error)

    def _ocultar_banner(self):
        if self.banner_error.visible:
            self.banner_error.visible = False
            self._actualizar_seguro(self.banner_error)

    def _plantilla_actual(self):
        return obtener_plantilla(self._plantilla_id)

    # ------------------------------------------------------------------
    # Fila de pasos (pills) — clic en uno ya completado regresa a ese paso
    # ------------------------------------------------------------------
    def _paso(self, numero: int, texto: str):
        activo = (not self._mostrando_resultado) and numero == self._paso_actual
        completado = self._mostrando_resultado or numero < self._paso_actual
        clickable = completado

        return ft.Container(
            width=200,
            ink=clickable,
            on_click=(lambda e, n=numero: self._on_click_paso(n)) if clickable else None,
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(ft.Icons.CHECK, color="#ffffff", size=16)
                        if completado
                        else ft.Text(str(numero), color="#ffffff", size=14, weight="bold"),
                        width=32,
                        height=32,
                        alignment=ft.Alignment(0, 0),
                        bgcolor="#7d8545" if completado else "#0d0905",
                        border_radius=16,
                    ),
                    ft.Text(
                        texto,
                        color="#1c1610" if activo else "#7c7267",
                        size=14,
                        weight="bold" if activo else "normal",
                        expand=True,
                    ),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor="#fbf5e9",
            border_radius=28,
            padding=ft.padding.symmetric(horizontal=14, vertical=9),
            shadow=ft.BoxShadow(
                blur_radius=10 if activo else 6,
                spread_radius=0,
                color=ft.Colors.with_opacity(0.20 if activo else 0.10, "#f4ca83"),
                offset=ft.Offset(0, 3),
            ),
        )

    def _on_click_paso(self, numero: int):
        if self._mostrando_resultado:
            self._mostrando_resultado = False
            self._ir_a(numero)
            return
        if numero >= self._paso_actual:
            return  # no se puede saltar a un paso que todavía no se completó
        self._ir_a(numero)

    # ------------------------------------------------------------------
    # Botones reutilizables (mismo lenguaje que el "Continuar" ya aprobado)
    # ------------------------------------------------------------------
    def _boton_principal(self, texto, on_click, *, habilitado=True, cargando=False,
                          texto_cargando="Generando...", icono=ft.Icons.AUTO_AWESOME):
        activo = habilitado and not cargando
        if cargando:
            contenido = ft.Row(
                controls=[
                    ft.ProgressRing(width=16, height=16, stroke_width=2, color="#f4ca83"),
                    ft.Text(texto_cargando, color="#ffffff", weight="bold", size=14),
                ],
                spacing=10,
            )
        else:
            contenido = ft.Row(
                controls=[
                    ft.Icon(icono, color="#ffa200" if habilitado else "#c9bda3", size=18),
                    ft.Text(
                        texto,
                        color="#ffffff" if habilitado else "#8a7e72",
                        size=14,
                        weight="bold",
                    ),
                ],
                spacing=8,
            )
        return ft.Container(
            content=contenido,
            bgcolor="#0d0905" if (habilitado or cargando) else "#eadfca",
            padding=ft.padding.symmetric(horizontal=24, vertical=13),
            border_radius=28,
            shadow=(
                ft.BoxShadow(
                    blur_radius=10,
                    color=ft.Colors.with_opacity(0.28, ft.Colors.BLACK),
                    offset=ft.Offset(0, 4),
                )
                if (habilitado or cargando)
                else None
            ),
            ink=activo,
            on_click=(on_click if activo else None),
        )

    def _boton_secundario(self, texto, on_click, icono=None):
        # Mismo par de colores que el botón "Cancelar" de _confirmar() en
        # dialogo_platillo.py — borde neutro, sin relleno.
        controles = []
        if icono:
            controles.append(ft.Icon(icono, size=16, color="#5e5449"))
        controles.append(ft.Text(texto, color="#5e5449", weight="bold", size=14))
        return ft.Container(
            content=ft.Row(controls=controles, spacing=8, tight=True,
                            alignment=ft.MainAxisAlignment.CENTER),
            bgcolor=ft.Colors.TRANSPARENT,
            border=ft.border.all(1, "#eadfca"),
            border_radius=28,
            padding=ft.padding.symmetric(horizontal=22, vertical=13),
            ink=True,
            on_click=on_click,
        )

    def _boton_atras(self, on_click):
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ARROW_BACK, size=14, color="#8a7e72"),
                    ft.Text("Atrás", color="#8a7e72", weight="bold", size=13),
                ],
                spacing=6,
            ),
            padding=ft.padding.symmetric(horizontal=10, vertical=8),
            border_radius=18,
            ink=True,
            on_click=on_click,
        )

    def _pie_paso(self, boton_principal, hint: str, boton_atras=None):
        """Fila de pie compartida por los 4 pasos: [Atrás] [hint] [acción]."""
        controles = []
        if boton_atras is not None:
            controles.append(boton_atras)
        controles.append(
            ft.Text(hint, size=13, color="#8a7e72", italic=True, expand=True)
        )
        controles.append(boton_principal)
        return ft.Row(controls=controles, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    # ------------------------------------------------------------------
    # Paso 1 — Diseño
    # ------------------------------------------------------------------
    def _pantalla_diseno(self):
        tarjetas = [self._tarjeta_plantilla(p) for p in self._plantillas]
        algo_elegido = self._plantilla_id is not None
        return ft.Column(
            spacing=0,
            controls=[
                ft.Text(
                    "Elige tu diseño",
                    size=22,
                    font_family="Georgia",
                    weight="bold",
                    italic=True,
                    color="#1c1610",
                ),
                ft.Text(
                    "Una de estas 4 plantillas es el fondo de tu anuncio.",
                    size=13,
                    color="#7c7267",
                ),
                ft.Container(height=22),
                ft.Row(
                    controls=tarjetas,
                    spacing=18,
                    alignment=ft.MainAxisAlignment.CENTER,
                    wrap=True,
                    run_spacing=18,
                ),
                ft.Container(height=26),
                self._pie_paso(
                    self._boton_principal(
                        "Continuar", self._on_continuar_diseno, habilitado=algo_elegido
                    ),
                    "Plantilla lista, dale continuar." if algo_elegido
                    else "Selecciona una plantilla para continuar.",
                ),
            ],
        )

    def _tarjeta_plantilla(self, plantilla):
        seleccionada = plantilla.id == self._plantilla_id
        return ft.Container(
            ink=True,
            border_radius=16,
            padding=6,
            on_click=lambda e, pid=plantilla.id: self._on_elegir_plantilla(pid),
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
                controls=[
                    ft.Container(
                        content=ft.Image(
                            src=plantilla.ruta_miniatura,
                            width=176,
                            height=198,
                            fit=ft.BoxFit.COVER,
                            border_radius=12,
                        ),
                        border_radius=14,
                        border=ft.border.all(3, "#d9ad4e") if seleccionada else None,
                        shadow=ft.BoxShadow(
                            blur_radius=10,
                            color=ft.Colors.with_opacity(0.22, ft.Colors.BLACK),
                            offset=ft.Offset(0, 4),
                        ),
                    ),
                    self._circulo_seleccion(seleccionada),
                    ft.Text(plantilla.nombre_bonito, size=11, color="#806f61"),
                ],
            ),
        )

    def _circulo_seleccion(self, seleccionada: bool):
        return ft.Container(
            width=24,
            height=24,
            border_radius=12,
            bgcolor="#d9ad4e" if seleccionada else "#fbf5e9",
            border=ft.border.all(2, "#d9ad4e"),
            alignment=ft.Alignment(0, 0),
            content=ft.Icon(ft.Icons.CHECK, size=14, color="#ffffff") if seleccionada else None,
        )

    def _on_elegir_plantilla(self, id_plantilla: str):
        if id_plantilla != self._plantilla_id:
            # Los campos de texto son específicos de cada plantilla
            # (headline_stack no es headline) -- un texto ya escrito para
            # otra plantilla no tiene sentido conservarlo.
            self._textos = {}
        self._plantilla_id = id_plantilla
        self._repintar_tarjeta()

    def _on_continuar_diseno(self, e):
        if self._plantilla_id is None:
            return
        self._ir_a(2)

    # ------------------------------------------------------------------
    # Paso 2 — Platillo (solo los que tienen recorte)
    # ------------------------------------------------------------------
    def _pantalla_platillo(self):
        if self._error_platillos:
            return self._contenido_error_platillos()

        if self._platillos_con_recorte is None:
            if not self._cargando_platillos:
                self._cargando_platillos = True
                self.router.page.run_task(self._cargar_platillos_con_recorte)
            return self._contenido_cargando_platillos()

        if not self._platillos_con_recorte:
            return self._contenido_sin_platillos()

        tarjetas = [self._tarjeta_platillo(p) for p in self._platillos_con_recorte]
        algo_elegido = self._platillo_id is not None
        return ft.Column(
            spacing=0,
            controls=[
                ft.Text(
                    "Elige el platillo",
                    size=22,
                    font_family="Georgia",
                    weight="bold",
                    italic=True,
                    color="#1c1610",
                ),
                ft.Text(
                    "Solo se muestran los platillos que ya tienen su foto "
                    "recortada lista.",
                    size=13,
                    color="#7c7267",
                ),
                ft.Container(height=22),
                ft.Row(
                    controls=tarjetas,
                    spacing=18,
                    alignment=ft.MainAxisAlignment.CENTER,
                    wrap=True,
                    run_spacing=18,
                ),
                ft.Container(height=26),
                self._pie_paso(
                    self._boton_principal(
                        "Continuar", self._on_continuar_platillo, habilitado=algo_elegido
                    ),
                    "Platillo listo, dale continuar." if algo_elegido
                    else "Selecciona un platillo para continuar.",
                    boton_atras=self._boton_atras(lambda e: self._ir_a(1)),
                ),
            ],
        )

    async def _cargar_platillos_con_recorte(self):
        try:
            datos = await asyncio.to_thread(PlatilloDAO.obtener_con_recorte)
        except httpx.RequestError as e:
            print(f"[contenido] error de red al traer platillos con recorte: {e}")
            self._error_platillos = True
        except Exception as e:
            print(f"[contenido] error inesperado al traer platillos con recorte: {e}")
            traceback.print_exc()
            self._error_platillos = True
        else:
            self._platillos_con_recorte = datos
        self._cargando_platillos = False
        if self._paso_actual == 2 and not self._mostrando_resultado:
            self._repintar_tarjeta()

    def _contenido_cargando_platillos(self):
        return ft.Column(
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
            controls=[
                ft.Container(height=20),
                ft.ProgressRing(width=28, height=28, stroke_width=3, color="#f4ca83"),
                ft.Text("Cargando tus platillos...", size=13, color="#7c7267"),
                ft.Container(height=20),
            ],
        )

    def _contenido_error_platillos(self):
        return ft.Column(
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
            controls=[
                ft.Container(height=10),
                ft.Icon(ft.Icons.ERROR_OUTLINE, size=30, color="#d9534f"),
                ft.Text(
                    "No se pudieron cargar los platillos.", size=14,
                    weight="bold", color="#5e5449",
                ),
                ft.Text("Revisa tu internet e intenta de nuevo.", size=12, color="#8a7e72"),
                ft.Container(height=14),
                self._boton_principal(
                    "Reintentar", self._on_reintentar_platillos, icono=ft.Icons.REFRESH
                ),
                ft.Container(height=6),
                self._boton_atras(lambda e: self._ir_a(1)),
            ],
        )

    def _on_reintentar_platillos(self, e):
        self._error_platillos = False
        self._platillos_con_recorte = None
        self._repintar_tarjeta()

    def _contenido_sin_platillos(self):
        return ft.Column(
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
            controls=[
                ft.Container(height=10),
                ft.Icon(ft.Icons.RESTAURANT_MENU_OUTLINED, size=30, color="#c9bda3"),
                ft.Text(
                    "Todavía no hay ningún platillo con foto recortada.",
                    size=14, weight="bold", color="#5e5449", text_align=ft.TextAlign.CENTER,
                ),
                ft.Text(
                    "Genera el recorte de un platillo desde \"Mi menú\" y vuelve aquí.",
                    size=12, color="#8a7e72", text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=14),
                self._boton_atras(lambda e: self._ir_a(1)),
            ],
        )

    def _tarjeta_platillo(self, platillo: dict):
        seleccionado = platillo.get("id") == self._platillo_id
        imagen = platillo.get("image_url_recortada") or "assets/sin-foto.png"
        return ft.Container(
            ink=True,
            border_radius=16,
            padding=6,
            on_click=lambda e, p=platillo: self._on_elegir_platillo(p),
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
                controls=[
                    ft.Container(
                        width=176,
                        height=198,
                        border_radius=14,
                        bgcolor="#f3ead4",
                        padding=8,
                        border=ft.border.all(3, "#d9ad4e") if seleccionado
                        else ft.border.all(1, "#eadfca"),
                        content=ft.Image(
                            src=imagen,
                            width=160,
                            height=182,
                            fit=ft.BoxFit.CONTAIN,
                            error_content=ft.Image(
                                src="assets/sin-foto.png", width=160, height=182,
                                fit=ft.BoxFit.CONTAIN,
                            ),
                        ),
                    ),
                    self._circulo_seleccion(seleccionado),
                    ft.Text(
                        platillo.get("nombre") or "", size=11, color="#806f61",
                        weight="bold", text_align=ft.TextAlign.CENTER,
                    ),
                ],
            ),
        )

    def _on_elegir_platillo(self, platillo: dict):
        self._platillo_id = platillo.get("id")
        self._platillo_seleccionado = platillo
        self._repintar_tarjeta()

    def _on_continuar_platillo(self, e):
        if self._platillo_id is None:
            return
        self._ir_a(3)

    # ------------------------------------------------------------------
    # Paso 3 — Texto (los campos cambian según la plantilla, trampa #6)
    # ------------------------------------------------------------------
    def _pantalla_texto(self):
        plantilla = self._plantilla_actual()
        campos = plantilla.campos_texto
        self._campos_texto_controles = {}

        controles_campos = []
        for campo in campos:
            control = self._campo_texto(campo)
            controles_campos.append(control)
            if campo == "headline_stack":
                controles_campos.append(ft.Container(height=6))
                controles_campos.append(
                    ft.Text(
                        "Escríbela una sola vez -- el diseño la repite solo "
                        "varias veces.",
                        size=11,
                        color="#8a7e72",
                        italic=True,
                        width=460,
                    )
                )
            controles_campos.append(ft.Container(height=16))
        if controles_campos:
            controles_campos.pop()  # quita el último espaciador sobrante

        return ft.Column(
            spacing=0,
            controls=[
                ft.Text(
                    "Escribe el texto",
                    size=22,
                    font_family="Georgia",
                    weight="bold",
                    italic=True,
                    color="#1c1610",
                ),
                ft.Text(
                    f'Así se verá en la plantilla "{plantilla.nombre_bonito}".',
                    size=13,
                    color="#7c7267",
                ),
                ft.Container(height=22),
                ft.Column(
                    controls=controles_campos,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=0,
                ),
                ft.Container(height=26),
                self._pie_paso(
                    self._boton_principal("Continuar", self._on_continuar_texto),
                    "Puedes regresar a este paso más tarde para cambiarlo.",
                    boton_atras=self._boton_atras(lambda e: self._ir_a(2)),
                ),
            ],
        )

    def _campo_texto(self, campo: str) -> ft.TextField:
        etiqueta, hint, icono = _CAMPOS_TEXTO[campo]
        control = ft.TextField(
            value=self._textos.get(campo, ""),
            hint_text=hint,
            prefix_icon=icono,
            width=460,
            height=52,
            border_radius=16,
            border_color="#eadfca",
            focused_border_color="#f4ca83",
            bgcolor="#f8f1de",
            color="#5e5449",
            hint_style=ft.TextStyle(color="#9b8f7e"),
            text_size=14,
            on_change=lambda e, c=campo: self._textos.__setitem__(c, e.control.value),
        )
        self._campos_texto_controles[campo] = control
        return control

    def _on_continuar_texto(self, e):
        plantilla = self._plantilla_actual()
        faltantes = []
        for campo in plantilla.campos_texto:
            valor = (self._campos_texto_controles[campo].value or "").strip()
            self._textos[campo] = valor
            if not valor:
                faltantes.append(_CAMPOS_TEXTO[campo][0])
        if faltantes:
            self._mostrar_banner(f"Completa: {', '.join(faltantes)}.")
            return
        self._ir_a(4)

    # ------------------------------------------------------------------
    # Paso 4 — Formato (post / historia) -- reusa el pill de "pestañas"
    # ------------------------------------------------------------------
    def _pantalla_formato(self):
        plantilla = self._plantilla_actual()
        opciones = [self._tarjeta_formato(plantilla.formato(fid)) for fid in FORMATOS]
        algo_elegido = self._formato_id is not None

        return ft.Column(
            spacing=0,
            controls=[
                ft.Text(
                    "Elige el formato",
                    size=22,
                    font_family="Georgia",
                    weight="bold",
                    italic=True,
                    color="#1c1610",
                ),
                ft.Text(
                    "¿Post normal para el feed, o historia vertical?",
                    size=13,
                    color="#7c7267",
                ),
                ft.Container(height=22),
                ft.Row(controls=opciones, spacing=18, alignment=ft.MainAxisAlignment.CENTER),
                ft.Container(height=26),
                self._pie_paso(
                    self._boton_principal(
                        "Generar anuncio",
                        self._on_generar_click,
                        habilitado=algo_elegido and not self._generando,
                        cargando=self._generando,
                    ),
                    "Se guardará solo en tu biblioteca al generarse." if algo_elegido
                    else "Selecciona un formato para continuar.",
                    boton_atras=self._boton_atras(lambda e: self._ir_a(3)),
                ),
            ],
        )

    def _tarjeta_formato(self, formato):
        # Mismo componente visual que la "pestaña" del wizard estático
        # (Continuo/Comida rápida) -- ver el docstring del módulo: ahí no
        # había datos reales que agrupar, aquí sí los hay (post/historia).
        activa = formato.id == self._formato_id
        ancho, alto = formato.canvas_referencia
        return ft.Container(
            ink=True,
            on_click=lambda e, fid=formato.id: self._on_elegir_formato(fid),
            content=ft.Column(
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=2,
                controls=[
                    ft.Text(
                        formato.nombre_bonito,
                        size=16,
                        color="#1c1610" if activa else "#8a7e72",
                        weight="bold" if activa else "normal",
                    ),
                    ft.Text(
                        f"{ancho} × {alto}",
                        size=11,
                        color="#8a7e72" if activa else "#a89a86",
                    ),
                ],
            ),
            bgcolor="#f8f1de" if activa else "#f4edde",
            padding=ft.padding.symmetric(horizontal=26, vertical=14),
            border_radius=22,
            border=ft.border.all(2, "#d9ad4e") if activa else None,
            shadow=ft.BoxShadow(
                blur_radius=8,
                spread_radius=0,
                color=ft.Colors.with_opacity(0.22 if activa else 0.08, "#030303"),
                offset=ft.Offset(0, 3),
            ),
        )

    def _on_elegir_formato(self, id_formato: str):
        self._formato_id = id_formato
        self._repintar_tarjeta()

    def _on_generar_click(self, e):
        if self._formato_id is None or self._generando:
            return
        self.router.page.run_task(self._generar)

    async def _generar(self):
        self._generando = True
        self._ocultar_banner()
        self._repintar_tarjeta()

        try:
            ruta = await asyncio.to_thread(
                generar_anuncio,
                self._plantilla_id,
                self._formato_id,
                self._platillo_seleccionado,
                dict(self._textos),
            )
        except httpx.RequestError as e:
            print(f"[contenido] error de red al generar el anuncio: {e}")
            self._generando = False
            self._mostrar_banner("No hay conexión con el servidor. Revisa tu internet.")
            self._repintar_tarjeta()
            return
        except ValueError as e:
            # Validación de generar_anuncio (faltó un campo de texto, o el
            # platillo no traía image_url_recortada) -- el mensaje ya sale
            # legible en español, se muestra tal cual.
            print(f"[contenido] validación al generar el anuncio: {e}")
            self._generando = False
            self._mostrar_banner(str(e))
            self._repintar_tarjeta()
            return
        except Exception as e:
            print(f"[contenido] error inesperado al generar el anuncio: {e}")
            traceback.print_exc()
            self._generando = False
            self._mostrar_banner("No se pudo generar el anuncio. Intenta de nuevo.")
            self._repintar_tarjeta()
            return

        self._generando = False
        self._ruta_generada = ruta
        self._mostrando_resultado = True
        self._repintar()

    # ------------------------------------------------------------------
    # Resultado -- ya generado y guardado (son el mismo acto, ver
    # generador_anuncios.py); no hay un paso/pill aparte para esto.
    # ------------------------------------------------------------------
    def _pantalla_resultado(self):
        formato = self._plantilla_actual().formato(self._formato_id)
        ancho_ref, alto_ref = formato.canvas_referencia
        alto_preview = 460
        ancho_preview = round(alto_preview * ancho_ref / alto_ref)

        return ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
            controls=[
                ft.Icon(ft.Icons.CHECK_CIRCLE, size=34, color="#7d8545"),
                ft.Container(height=10),
                ft.Text(
                    "¡Tu anuncio ya está listo!",
                    size=22,
                    font_family="Georgia",
                    italic=True,
                    weight="bold",
                    color="#1c1610",
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Text(
                    "Se guardó automáticamente en tu biblioteca -- no hace "
                    "falta guardarlo aparte.",
                    size=13,
                    color="#7c7267",
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=22),
                ft.Container(
                    bgcolor="#eee5cf",
                    border_radius=14,
                    padding=8,
                    shadow=ft.BoxShadow(
                        blur_radius=14,
                        color=ft.Colors.with_opacity(0.22, ft.Colors.BLACK),
                        offset=ft.Offset(0, 5),
                    ),
                    content=ft.Image(
                        src=self._ruta_generada,
                        width=ancho_preview,
                        height=alto_preview,
                        fit=ft.BoxFit.CONTAIN,
                        border_radius=8,
                    ),
                ),
                ft.Container(height=26),
                ft.Row(
                    controls=[
                        self._boton_secundario(
                            "Crear otro anuncio", self._on_crear_otro, icono=ft.Icons.REFRESH
                        ),
                        self._boton_principal(
                            "Ver en la biblioteca", self._on_ver_biblioteca,
                            icono=ft.Icons.ARROW_FORWARD,
                        ),
                    ],
                    spacing=14,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
            ],
        )

    def _on_crear_otro(self, e):
        self._plantilla_id = None
        self._platillo_id = None
        self._platillo_seleccionado = None
        self._textos = {}
        self._formato_id = None
        self._ruta_generada = None
        self._mostrando_resultado = False
        self._ir_a(1)

    def _on_ver_biblioteca(self, e):
        self.router.cambiar_vista("biblioteca")
