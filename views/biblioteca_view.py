"""
views/biblioteca_view.py
Fase 7.4 — la galería de lo generado. Vuelve real la pantalla de relleno:
lee la carpeta biblioteca/ del proyecto (la misma que
models/generador_anuncios.py escribe al componer un anuncio, Fase 7.2) y
pinta una tarjeta por imagen, con ver/exportar/borrar. Mismo lenguaje
visual que el resto del panel — tarjeta #f8f1de, sombra, badges y botones
ya establecidos — nada de esto se rediseñó.

REFERENCIA (roadmap, bloque "LA REFERENCIA"): EJEMPLOS 2/views/
biblioteca_view.py usa GridView(max_extent=300, child_aspect_ratio=0.8),
lista con os.listdir filtrando extensiones, y trae descargar+borrar por
tarjeta. Se adapta, no se copia: la paleta/tipografía son las de este
proyecto, "descargar" se vuelve "exportar" a la ruta secundaria (ver la
nota de ALCANCE más abajo) y se agrega "ver" en grande, que la referencia
no tenía.

⚠️ ESTA VISTA RECARGA EN __init__, NO EN did_mount() -- una diferencia
deliberada frente a la referencia, no un descuido. La referencia necesita
did_mount() porque su router reutiliza LA MISMA instancia de vista al
volver a ella; aquí no: controllers/main_controller.py.cambiar_vista()
instancia una vista NUEVA en cada navegación (ver CLAUDE.md → Architecture,
"MVC-ish structure" -- "Views are rebuilt from scratch on every
navigation"), así que __init__ YA se vuelve a ejecutar solo con volver a
"Mi biblioteca" desde el sidebar o desde el botón "Ver en la biblioteca"
del resultado de contenido_view.py. Un did_mount() aquí sería trabajo
repetido, no una corrección.

ALCANCE DE "EXPORTAR" -- decidido explícitamente en el prompt de esta
fase en vez de dejar el botón deshabilitado: la ruta secundaria que
configura ajustes_view.py (Fase 7.5) TODAVÍA NO TIENE PANTALLA -- lo que
sí existe es el pedacito de lógica que hacía falta,
models/config_usuario.py (nuevo, junto con esta vista), que lee/guarda esa
ruta fuera del repo con fallback a ~/Downloads. "Exportar" ya funciona hoy
mismo copiando a ~/Downloads (o a lo que el dueño configure una vez que
exista la 7.5, sin tocar esta vista) en vez de quedarse inerte con una
nota -- exportar-a-Descargas por default es un resultado útil por sí
mismo, no solo un relleno.
"""
import asyncio
import datetime
import os
import shutil
import traceback

import flet as ft

from models.config_usuario import obtener_ruta_exportacion
from models.generador_anuncios import RUTA_BIBLIOTECA
from views.components.dialogo_platillo import _confirmar

_EXTENSIONES_VALIDAS = (".png", ".jpg", ".jpeg", ".webp")

_MESES_MIN = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _listar_anuncios() -> list[dict]:
    """Lee RUTA_BIBLIOTECA del disco -- carpeta AUSENTE se trata igual que
    "vacío", nunca como error: generar_anuncio() (Fase 7.2) la crea con
    os.makedirs(..., exist_ok=True) la primera vez que se genera un
    anuncio, así que en un panel recién instalado, o en uno donde el dueño
    todavía no genera nada, sencillamente no existe todavía. Ordenada del
    más reciente al más viejo por fecha de modificación real del archivo
    -- no por el timestamp en su nombre, que asume un formato que solo
    generador_anuncios.py garantiza (ver _slug()/_ruta_salida() ahí) y que
    un archivo suelto que alguien copie a mano a esta carpeta no tendría
    por qué respetar."""
    if not os.path.isdir(RUTA_BIBLIOTECA):
        return []
    anuncios = []
    for nombre_archivo in os.listdir(RUTA_BIBLIOTECA):
        if not nombre_archivo.lower().endswith(_EXTENSIONES_VALIDAS):
            continue
        ruta = f"{RUTA_BIBLIOTECA}/{nombre_archivo}"
        try:
            mtime = os.path.getmtime(ruta)
        except OSError:
            continue  # el archivo desapareció entre el listdir y aquí
        anuncios.append({"ruta": ruta, "nombre_archivo": nombre_archivo, "mtime": mtime})
    anuncios.sort(key=lambda a: a["mtime"], reverse=True)
    return anuncios


def _tiempo_relativo_local(mtime: float) -> str:
    """Mismo lenguaje que _tiempo_relativo() de home_view.py ("hace N
    minutos" / "ayer" / "el D de mes"), pero SIN su conversión UTC->local:
    esa conversión existe allá porque Supabase entrega timestamps en UTC;
    os.path.getmtime() ya regresa la hora del reloj de ESTA máquina (es el
    filesystem local), así que repetir la conversión correría el riesgo de
    desfasarla en vez de corregirla."""
    fecha = datetime.datetime.fromtimestamp(mtime)
    ahora = datetime.datetime.now()
    segundos = (ahora - fecha).total_seconds()

    if segundos < 60:
        return "hace un momento"
    if segundos < 3600:
        minutos = int(segundos // 60)
        return "hace 1 minuto" if minutos == 1 else f"hace {minutos} minutos"

    dias_diferencia = (ahora.date() - fecha.date()).days
    if dias_diferencia <= 0:
        horas = int(segundos // 3600)
        return "hace 1 hora" if horas == 1 else f"hace {horas} horas"
    if dias_diferencia == 1:
        return "ayer"
    if dias_diferencia < 7:
        return f"hace {dias_diferencia} días"
    return f"el {fecha.day} de {_MESES_MIN[fecha.month - 1]}"


def _texto_contador(cantidad: int) -> str:
    if cantidad == 1:
        return "1 anuncio guardado"
    return f"{cantidad} anuncios guardados"


def _ver_imagen(page: ft.Page, ruta: str, nombre_archivo: str):
    """Diálogo de "ver en grande" -- mismo patrón de X explícita que
    DialogoPlatillo/_confirmar() (dialogo_platillo.py): modal=True bloquea
    tap-fuera y Escape en esta versión de flet, así que sin un botón de
    cerrar no habría forma de salir del diálogo."""

    def _cerrar(e=None):
        page.pop_dialog()

    boton_cerrar = ft.Container(
        content=ft.Icon(ft.Icons.CLOSE, size=16, color="#756b5e"),
        width=30,
        height=30,
        border_radius=15,
        ink=True,
        alignment=ft.Alignment(0, 0),
        on_click=_cerrar,
        top=10,
        right=10,
        tooltip="Cerrar",
    )

    dialogo = ft.AlertDialog(
        modal=True,
        bgcolor="#f8f1de",
        shape=ft.RoundedRectangleBorder(radius=16),
        content_padding=ft.padding.symmetric(horizontal=20, vertical=20),
        content=ft.Stack(
            controls=[
                ft.Column(
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=10,
                    controls=[
                        ft.Container(
                            bgcolor="#eee5cf",
                            border_radius=10,
                            padding=8,
                            content=ft.Image(
                                src=ruta,
                                width=440,
                                height=620,
                                fit=ft.BoxFit.CONTAIN,
                                border_radius=6,
                            ),
                        ),
                        ft.Text(
                            nombre_archivo,
                            size=12,
                            color="#8a7e72",
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            width=456,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                ),
                boton_cerrar,
            ],
        ),
    )
    page.show_dialog(dialogo)


class BibliotecaView(ft.Container):
    def __init__(self, router):
        super().__init__()
        self.router = router
        self.expand = True
        self.height = float("inf")
        self.bgcolor = "#fbf5e9"
        self.padding = ft.padding.only(left=36, right=36, top=42, bottom=36)

        dias = ["LUNES", "MARTES", "MIÉRCOLES", "JUEVES", "VIERNES", "SÁBADO", "DOMINGO"]
        meses = [
            "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
            "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE",
        ]
        hoy = datetime.datetime.now()
        fecha_texto = f"{dias[hoy.weekday()]}, {hoy.day} DE {meses[hoy.month - 1]}"

        # Banner temporal de error -- mismo patrón que mesas_view.py
        # (_mostrar_error_temporal): exportar/borrar no tienen un diálogo
        # propio donde pintar la caja de error.
        self._banner_token = 0
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

        self.texto_subtitulo = ft.Text("", size=15, color="#7c7267")

        # Se lee del disco AQUÍ, en __init__ -- ver el docstring del
        # módulo sobre por qué did_mount() no hace falta en este proyecto.
        try:
            self._anuncios = _listar_anuncios()
            error_al_listar = False
        except OSError as e:
            print(f"[biblioteca] error al listar {RUTA_BIBLIOTECA}: {e}")
            self._anuncios = []
            error_al_listar = True

        self.cuerpo = ft.Column(expand=True, spacing=0)

        self.content = ft.Column(
            expand=True,
            height=float("inf"),
            spacing=0,
            controls=[
                ft.Text(fecha_texto, size=13, weight="bold", color="#b58a6d"),
                ft.Text(
                    "Mi biblioteca",
                    size=42,
                    font_family="Georgia",
                    italic=True,
                    color="#18120d",
                ),
                self.texto_subtitulo,
                ft.Container(height=18),
                self.banner_error,
                ft.Container(height=6),
                self.cuerpo,
            ],
        )

        if error_al_listar:
            self._mostrar_error_carga()
        else:
            self._repintar()

    # ------------------------------------------------------------------
    # Armado del cuerpo: grid / vacío / error
    # ------------------------------------------------------------------
    def _repintar(self):
        if not self._anuncios:
            self.texto_subtitulo.value = "Guarda y organiza el contenido que creas para tu negocio."
            self.cuerpo.controls = [self._estado_vacio()]
        else:
            self.texto_subtitulo.value = _texto_contador(len(self._anuncios))
            self.cuerpo.controls = [self._grid()]
        self._actualizar_seguro(self.texto_subtitulo, self.cuerpo)

    def _mostrar_error_carga(self):
        self.texto_subtitulo.value = "No se pudo leer tu biblioteca."
        self.cuerpo.controls = [
            ft.Container(
                expand=True,
                bgcolor="#f8f1de",
                border_radius=24,
                alignment=ft.Alignment(0, 0),
                content=ft.Column(
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                    controls=[
                        ft.Icon(ft.Icons.ERROR_OUTLINE, size=30, color="#d9534f"),
                        ft.Text(
                            "No se pudo abrir la carpeta de tu biblioteca.",
                            size=14, weight="bold", color="#5e5449",
                        ),
                        ft.Text(
                            "Revisa los permisos de la carpeta \"biblioteca\" e intenta de nuevo.",
                            size=12, color="#8a7e72",
                        ),
                    ],
                ),
            )
        ]
        self._actualizar_seguro(self.texto_subtitulo, self.cuerpo)

    def _actualizar_seguro(self, *controles):
        """Igual que en contenido_view.py/agenteIA_view.py: si el dueño ya
        navegó a otra pantalla mientras una tarea en vuelo (exportar/
        borrar) seguía corriendo, esta vista quedó desmontada y .update()
        lanzaría una excepción que no vería nadie."""
        for control in controles:
            try:
                control.update()
            except Exception:
                pass

    def _estado_vacio(self):
        return ft.Container(
            expand=True,
            bgcolor="#f8f1de",
            border_radius=24,
            shadow=ft.BoxShadow(
                blur_radius=20,
                spread_radius=0,
                color=ft.Colors.with_opacity(0.20, "#f4ca83"),
                offset=ft.Offset(0, 6),
            ),
            alignment=ft.Alignment(0, 0),
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                controls=[
                    ft.Text(
                        "Tu biblioteca está vacía",
                        size=25,
                        font_family="Georgia",
                        weight="bold",
                        italic=True,
                        color="#1c1610",
                    ),
                    ft.Text(
                        "Aquí aparecerán tus publicaciones y materiales generados.",
                        size=14,
                        color="#7c7267",
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=8),
                    ft.Container(
                        width=230,
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.AUTO_AWESOME, color="#f4ca83", size=18),
                                ft.Text("Crear contenido", color="#ffffff", size=14, weight="bold"),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=8,
                        ),
                        bgcolor="#0d0905",
                        padding=ft.padding.symmetric(horizontal=18, vertical=11),
                        border_radius=26,
                        shadow=ft.BoxShadow(
                            blur_radius=10,
                            color=ft.Colors.with_opacity(0.28, ft.Colors.BLACK),
                            offset=ft.Offset(0, 4),
                        ),
                        ink=True,
                        on_click=lambda _: self.router.cambiar_vista("contenido"),
                    ),
                ],
            ),
        )

    def _grid(self):
        return ft.GridView(
            expand=True,
            max_extent=260,
            child_aspect_ratio=0.72,
            spacing=18,
            run_spacing=18,
            padding=ft.padding.only(top=4, bottom=12),
            controls=[self._tarjeta_anuncio(a) for a in self._anuncios],
        )

    # ------------------------------------------------------------------
    # Tarjeta de un anuncio
    # ------------------------------------------------------------------
    def _tarjeta_anuncio(self, anuncio: dict):
        ruta = anuncio["ruta"]
        nombre_archivo = anuncio["nombre_archivo"]
        return ft.Container(
            bgcolor="#f8f1de",
            border_radius=16,
            padding=10,
            shadow=ft.BoxShadow(
                blur_radius=10,
                spread_radius=0,
                color=ft.Colors.with_opacity(0.14, "#030303"),
                offset=ft.Offset(0, 3),
            ),
            content=ft.Column(
                spacing=8,
                controls=[
                    ft.Container(
                        expand=True,
                        bgcolor="#eee5cf",
                        border_radius=12,
                        padding=6,
                        ink=True,
                        on_click=lambda e, r=ruta, n=nombre_archivo: _ver_imagen(
                            self.router.page, r, n
                        ),
                        content=ft.Image(
                            src=ruta,
                            fit=ft.BoxFit.CONTAIN,
                            border_radius=8,
                            error_content=ft.Icon(
                                ft.Icons.BROKEN_IMAGE_OUTLINED, size=30, color="#c9bda3"
                            ),
                        ),
                        tooltip="Ver en grande",
                    ),
                    ft.Text(
                        _tiempo_relativo_local(anuncio["mtime"]),
                        size=11,
                        color="#8a7e72",
                    ),
                    ft.Row(
                        controls=[
                            self._accion(
                                ft.Icons.VISIBILITY_OUTLINED,
                                on_click=lambda e, r=ruta, n=nombre_archivo: _ver_imagen(
                                    self.router.page, r, n
                                ),
                                tooltip="Ver en grande",
                            ),
                            self._accion(
                                ft.Icons.IOS_SHARE,
                                on_click=lambda e, a=anuncio: self._on_exportar_click(a),
                                tooltip="Exportar",
                            ),
                            self._accion(
                                ft.Icons.DELETE_OUTLINE,
                                on_click=lambda e, a=anuncio: self._on_eliminar_click(a),
                                tooltip="Eliminar",
                                color="#a33c39",
                            ),
                        ],
                        spacing=4,
                        alignment=ft.MainAxisAlignment.END,
                    ),
                ],
            ),
        )

    def _accion(self, icono: str, on_click=None, tooltip: str = None, color: str = "#756b5e"):
        # Mismo botón de acción 30x30/border_radius=15/ink=True que ya
        # usan menu_view.py y mesas_view.py -- el único color que cambia
        # es el de "Eliminar", igual que su lápiz/ojo/basura.
        return ft.Container(
            content=ft.Icon(icono, size=16, color=color),
            width=30,
            height=30,
            alignment=ft.Alignment(0, 0),
            border_radius=15,
            ink=True,
            on_click=on_click,
            tooltip=tooltip,
        )

    # ------------------------------------------------------------------
    # Exportar -- copia el archivo real a la ruta secundaria (ver la nota
    # de ALCANCE en el docstring del módulo)
    # ------------------------------------------------------------------
    def _on_exportar_click(self, anuncio: dict):
        self.router.page.run_task(self._exportar_async, anuncio)

    async def _exportar_async(self, anuncio: dict):
        destino_carpeta = obtener_ruta_exportacion()
        destino = os.path.join(destino_carpeta, anuncio["nombre_archivo"])
        try:
            await asyncio.to_thread(shutil.copy2, anuncio["ruta"], destino)
        except OSError as e:
            print(f"[biblioteca] error al exportar a {destino_carpeta}: {e}")
            self._mostrar_error_temporal(
                f'No se pudo copiar a "{destino_carpeta}". Revisa que la '
                "carpeta exista y que tengas permiso para escribir en ella."
            )
            return
        except Exception as e:
            print(f"[biblioteca] error inesperado al exportar: {e}")
            traceback.print_exc()
            self._mostrar_error_temporal("No se pudo exportar el archivo. Intenta de nuevo.")
            return
        # Sin banner de éxito (el proyecto no tiene un segundo lenguaje
        # visual de "aviso" además del rojo de error, ver
        # dialogo_platillo.py/models/cloudflare_storage.py) -- en su lugar
        # el ícono del botón confirma con un check, mismo idioma visual
        # ligero de "acción hecha" que ya usan los pills de contenido_view.py.
        self._confirmar_exportado_visualmente(anuncio)

    def _confirmar_exportado_visualmente(self, anuncio: dict):
        """Encuentra la tarjeta de este anuncio y le prende un check verde
        en el botón de exportar por un momento, en vez de un banner --
        exportar es una acción de cortesía sin nada que decidir después,
        no amerita interrumpir la vista con un aviso que hay que descartar
        a mano. self.cuerpo.controls[0] es el GridView de _grid() -- sus
        índices coinciden 1:1 con self._anuncios porque ambos se
        reconstruyen juntos en _repintar(); no se toca nada más de la
        tarjeta, solo el ícono de ese botón."""
        if not self.cuerpo.controls:
            return
        grid = self.cuerpo.controls[0]
        for indice, a in enumerate(self._anuncios):
            if a["ruta"] == anuncio["ruta"] and indice < len(grid.controls):
                boton_exportar = grid.controls[indice].content.controls[-1].controls[1]
                boton_exportar.content = ft.Icon(ft.Icons.CHECK, size=16, color="#7d8545")
                self._actualizar_seguro(boton_exportar)
                self.router.page.run_task(self._restaurar_icono_exportar, anuncio["ruta"])
                return

    async def _restaurar_icono_exportar(self, ruta: str, espera_seg: float = 1.6):
        await asyncio.sleep(espera_seg)
        if not self.cuerpo.controls:
            return
        grid = self.cuerpo.controls[0]
        for indice, a in enumerate(self._anuncios):
            if a["ruta"] == ruta and indice < len(grid.controls):
                boton_exportar = grid.controls[indice].content.controls[-1].controls[1]
                boton_exportar.content = ft.Icon(ft.Icons.IOS_SHARE, size=16, color="#756b5e")
                self._actualizar_seguro(boton_exportar)
                return

    # ------------------------------------------------------------------
    # Borrar -- el archivo real de disco, con la misma confirmación que
    # ya usan menu_view.py (platillos) y mesas_view.py (mesas)
    # ------------------------------------------------------------------
    def _on_eliminar_click(self, anuncio: dict):
        _confirmar(
            self.router.page,
            titulo="¿Eliminar este anuncio?",
            mensaje=(
                f'"{anuncio["nombre_archivo"]}" se borrará de tu biblioteca '
                "de forma permanente. Esta acción no se puede deshacer."
            ),
            on_confirmar=lambda: self.router.page.run_task(self._eliminar_async, anuncio),
        )

    async def _eliminar_async(self, anuncio: dict):
        try:
            await asyncio.to_thread(os.remove, anuncio["ruta"])
        except OSError as e:
            print(f"[biblioteca] error al eliminar {anuncio['ruta']}: {e}")
            self._mostrar_error_temporal("No se pudo eliminar el archivo. Intenta de nuevo.")
            return
        self._anuncios = [a for a in self._anuncios if a["ruta"] != anuncio["ruta"]]
        self._repintar()

    # ------------------------------------------------------------------
    def _mostrar_error_temporal(self, mensaje: str, duracion_seg: int = 4):
        self._banner_token += 1
        token = self._banner_token
        self.texto_banner_error.value = mensaje
        self.banner_error.visible = True
        self._actualizar_seguro(self.banner_error)
        self.router.page.run_task(self._ocultar_banner_luego, token, duracion_seg)

    async def _ocultar_banner_luego(self, token: int, duracion_seg: int):
        await asyncio.sleep(duracion_seg)
        if token != self._banner_token:
            return
        self.banner_error.visible = False
        self._actualizar_seguro(self.banner_error)
