"""
views/ajustes_view.py
Fase 7.5 — la pantalla deja de ser relleno: conecta la ruta secundaria de
exportación con models/config_usuario.py (Fase 7.4). Abajo, la tarjeta
del tema (ver TEMA).

El layout visual (tarjeta, TextField, botón de carpeta, botón "Guardar
ajustes") ya estaba aprobado desde antes de esta fase — no se tocó nada de
eso, solo se conectó. Lo único que se agregó de forma nueva es la caja de
error (mismo patrón #f7e4e3/#d9534f/#a33c39 que ya usan sesion_view.py/
dialogo_platillo.py/biblioteca_view.py) y la tarjeta de abajo (hoy, TEMA).

REFERENCIA (roadmap, bloque "CÓMO SE ARMA" → "LOS AJUSTES"): EJEMPLOS 2/
views/ajustes_view.py usa un TextField read_only=True + un botón de carpeta
que abre Tkinter (filedialog.askdirectory(), root.withdraw(),
root.attributes('-topmost', True) — misma técnica que
_elegir_archivo_imagen() en dialogo_platillo.py, solo que para una carpeta
en vez de un archivo) y guarda con os.path.normpath() al pulsar "Guardar
Ajustes", nunca en cuanto Tkinter regresa. Esa forma se adapta tal cual;
lo único que cambia es DÓNDE se persiste — ver models/config_usuario.py,
que ya resolvió esa pregunta en la Fase 7.4 (%LOCALAPPDATA%\\TakuMonky\\
config.json, no un config.json en la raíz del repo público).

EL BOTÓN DE ELEGIR CARPETA actualiza el TextField de inmediato (para que
el dueño vea qué eligió), pero NO escribe nada en disco todavía — mismo
criterio que _elegir_foto_async() en dialogo_platillo.py, que muestra la
miniatura antes de que exista ningún guardado real. Solo "Guardar ajustes"
llama a guardar_ruta_exportacion().

TEMA (28/09, pedido del dueño, como en Anxie): la tarjeta de abajo, que
antes era "Cuenta" con "Cerrar sesión", ahora elige el tema (oscuro/claro)
con el interruptor de views/piezas.py. Al elegir otro, el botón del
interruptor se desliza y luego router.cambiar_tema() lo guarda en
config.json (clave "tema") y rehace Ajustes con los colores nuevos. Cerrar
sesión sigue en la barra lateral (views/barra_lateral.py).
"""
import asyncio
import datetime
import os
import tkinter as tk
import traceback
from tkinter import filedialog

import flet as ft

from views import tema
from views.piezas import fondo_pagina, interruptor
from views.tema import C

from models.config_usuario import guardar_ruta_exportacion, obtener_ruta_exportacion


# Los temas del panel (views/tema.py), en el orden del interruptor: texto,
# icono y su nombre en config.json. Los mismos que Anxie.
TEMAS = [
    ("Oscuro", ft.Icons.DARK_MODE_OUTLINED, "oscuro"),
    ("Claro", ft.Icons.LIGHT_MODE_OUTLINED, "claro"),
]


def _elegir_carpeta_exportacion() -> str | None:
    """Abre el selector de carpetas NATIVO de Windows vía Tkinter — misma
    técnica que _elegir_archivo_imagen() en dialogo_platillo.py, adaptada
    a una carpeta (askdirectory en vez de askopenfilename). Devuelve la
    ruta elegida o None si el dueño cerró/canceló el diálogo.

    BLOQUEANTE de verdad (congela el hilo que la llama hasta que se cierra
    el diálogo) — SIEMPRE se invoca vía asyncio.to_thread desde
    _elegir_carpeta_async(), nunca directo desde un on_click, o congelaría
    también la ventana de Flet mientras el selector está abierto."""
    raiz = tk.Tk()
    raiz.withdraw()
    raiz.attributes("-topmost", True)  # que no se abra detrás de la ventana de Flet
    try:
        ruta = filedialog.askdirectory(title="Selecciona la carpeta de exportación")
    finally:
        raiz.destroy()
    return ruta or None


class AjustesView(ft.Container):
    def __init__(self, router):
        super().__init__()
        self.router = router
        self.expand = True
        self.height = float("inf")
        self.bgcolor = C.fondo
        self.gradient = fondo_pagina()
        self.padding = ft.Padding.only(left=36, right=36, top=42, bottom=36)

        # True mientras el selector de Tkinter está abierto o se está
        # guardando el ajuste — acciones exclusivas entre sí en esta
        # pantalla tan chica.
        self._ocupado = False
        self._banner_token = 0

        dias = ["LUNES", "MARTES", "MIÉRCOLES", "JUEVES", "VIERNES", "SÁBADO", "DOMINGO"]
        meses = [
            "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
            "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE",
        ]
        hoy = datetime.datetime.now()
        fecha_texto = f"{dias[hoy.weekday()]}, {hoy.day} DE {meses[hoy.month - 1]}"

        # Precarga con la ruta YA guardada (o el respaldo a ~/Downloads si
        # el dueño nunca configuró nada) — la misma función que ya usa
        # biblioteca_view.py para "Exportar", así que las dos pantallas
        # arrancan mostrando exactamente el mismo destino.
        self.ruta_exportacion = ft.TextField(
            value=obtener_ruta_exportacion(),
            read_only=True,
            height=54,
            expand=True,
            border=ft.InputBorder.OUTLINE,
            border_radius=14,
            border_color=C.linea,
            focused_border_color=C.texto,
            bgcolor=C.fondo,
            color=C.texto,
            text_size=14,
            content_padding=ft.Padding.symmetric(horizontal=16, vertical=14),
        )

        self.boton_carpeta = ft.Container(
            content=ft.Icon(ft.Icons.FOLDER_OPEN_OUTLINED, color=C.texto, size=24),
            width=54,
            height=54,
            alignment=ft.Alignment(0, 0),
            border_radius=27,
            ink=True,
            on_click=self._on_elegir_carpeta_click,
            tooltip="Elegir carpeta",
        )

        # Caja de error — mismo patrón #f7e4e3/#d9534f/#a33c39 que ya usan
        # sesion_view.py/dialogo_platillo.py/biblioteca_view.py. Temporal
        # (se oculta sola), como en biblioteca_view.py/mesas_view.py: esta
        # pantalla no tiene un diálogo propio donde dejar el error fijo.
        self.texto_error = ft.Text("", size=12, color=C.texto_suave, expand=True)
        self.zona_error = ft.Container(
            visible=False,
            bgcolor=C.pozo,
            border=ft.Border.all(1, C.texto_suave),
            border_radius=12,
            padding=ft.Padding.symmetric(horizontal=12, vertical=10),
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE, size=15, color=C.texto_suave),
                    self.texto_error,
                ],
                spacing=8,
            ),
        )

        self._texto_boton_guardar = ft.Row(
            controls=[
                ft.Icon(ft.Icons.SAVE_OUTLINED, color=C.texto, size=18),
                ft.Text("Guardar ajustes", color=C.texto, size=14, font_family="LetraTitulo"),
            ],
            spacing=8,
            tight=True,
        )
        self.boton_guardar = ft.Container(
            content=self._texto_boton_guardar,
            bgcolor=C.cara_encendida,
            padding=ft.Padding.symmetric(horizontal=22, vertical=13),
            border_radius=28,
            shadow=ft.BoxShadow(
                blur_radius=10,
                color=C.sombra,
                offset=ft.Offset(0, 4),
            ),
            ink=True,
            on_click=self._on_guardar_click,
        )

        # El interruptor del tema (Oscuro / Claro), el mismo de views/piezas.py
        # que usa Anxie en su tarjeta TEMA. Va donde estaba "Cerrar sesión".
        self.selector_tema = interruptor(
            [(texto, icono) for texto, icono, _ in TEMAS],
            [nombre for _, _, nombre in TEMAS].index(tema.actual()),
            self._on_cambiar_tema,
        )

        self.content = ft.Column(
            expand=True,
            height=float("inf"),
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.Text(fecha_texto, size=13, font_family="LetraTitulo", color=C.texto_suave),
                ft.Text(
                    "Ajustes",
                    size=42,
                    font_family="LetraTitulo",
                    color=C.texto,
                ),
                ft.Text(
                    "Configura dónde se guardará el contenido que generes.",
                    size=15,
                    color=C.texto_suave,
                ),
                ft.Container(height=30),
                ft.Container(
                    bgcolor=C.cara,
                    border_radius=24,
                    padding=ft.Padding.only(left=28, right=28, top=28, bottom=28),
                    shadow=ft.BoxShadow(
                        blur_radius=18,
                        spread_radius=0,
                        color=C.sombra,
                        offset=ft.Offset(0, 6),
                    ),
                    content=ft.Column(
                        spacing=0,
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Container(
                                        content=ft.Icon(ft.Icons.FOLDER_OUTLINED, color=C.texto, size=22),
                                        width=44,
                                        height=44,
                                        alignment=ft.Alignment(0, 0),
                                        bgcolor=C.cara_encendida,
                                        border_radius=22,
                                    ),
                                    ft.Column(
                                        expand=True,
                                        spacing=2,
                                        controls=[
                                            ft.Text(
                                                "Exportaciones locales",
                                                size=22,
                                                font_family="LetraTitulo",
                                                color=C.texto,
                                            ),
                                            ft.Text(
                                                "Define la carpeta donde se guardarán tus imágenes y publicaciones.",
                                                size=13,
                                                color=C.texto_suave,
                                            ),
                                        ],
                                    ),
                                ],
                                spacing=14,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.Container(height=26),
                            ft.Divider(height=1, color=C.linea),
                            ft.Container(height=24),
                            ft.Text(
                                "Ruta para exportar contenido",
                                size=14,
                                font_family="LetraTitulo",
                                color=C.texto,
                            ),
                            ft.Container(height=8),
                            ft.Row(
                                controls=[
                                    self.ruta_exportacion,
                                    self.boton_carpeta,
                                ],
                                spacing=12,
                            ),
                            ft.Container(height=14),
                            self.zona_error,
                            ft.Container(height=16),
                            ft.Row(
                                controls=[
                                    ft.Text(
                                        "Elige una carpeta accesible desde esta computadora.",
                                        size=12,
                                        color=C.texto_suave,
                                        expand=True,
                                    ),
                                    self.boton_guardar,
                                ],
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                        ],
                    ),
                ),
                ft.Container(height=24),
                ft.Container(
                    bgcolor=C.cara,
                    border_radius=24,
                    padding=ft.Padding.only(left=28, right=28, top=24, bottom=24),
                    shadow=ft.BoxShadow(
                        blur_radius=18,
                        spread_radius=0,
                        color=C.sombra,
                        offset=ft.Offset(0, 4),
                    ),
                    content=ft.Row(
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Container(
                                content=ft.Icon(ft.Icons.CONTRAST_ROUNDED, color=C.texto_suave, size=20),
                                width=44,
                                height=44,
                                alignment=ft.Alignment(0, 0),
                                bgcolor=C.cara,
                                border_radius=22,
                            ),
                            ft.Container(width=14),
                            ft.Column(
                                expand=True,
                                spacing=2,
                                controls=[
                                    ft.Text(
                                        "Tema",
                                        size=20,
                                        font_family="LetraTitulo",
                                        color=C.texto,
                                    ),
                                    ft.Text(
                                        "Los colores del panel: oscuro o claro.",
                                        size=13,
                                        color=C.texto_suave,
                                    ),
                                ],
                            ),
                            self.selector_tema,
                        ],
                    ),
                ),
                ft.Container(height=24),
            ],
        )

    # ------------------------------------------------------------------
    # Elegir carpeta (Tkinter, vía asyncio.to_thread)
    # ------------------------------------------------------------------
    def _on_elegir_carpeta_click(self, e):
        if self._ocupado:
            return  # ya hay un selector abierto, un guardado o un cierre de sesión en curso
        self.router.page.run_task(self._elegir_carpeta_async)

    async def _elegir_carpeta_async(self):
        self._ocupado = True
        self.boton_carpeta.disabled = True
        self._actualizar_seguro(self.boton_carpeta)
        try:
            # _elegir_carpeta_exportacion() es bloqueante de verdad (el
            # diálogo nativo de Windows) — a un hilo aparte, o congelaría
            # la ventana de Flet mientras el dueño elige la carpeta.
            ruta = await asyncio.to_thread(_elegir_carpeta_exportacion)
        finally:
            self._ocupado = False
            self.boton_carpeta.disabled = False
            self._actualizar_seguro(self.boton_carpeta)

        if not ruta:
            return  # el dueño cerró/canceló el selector de carpetas

        # Se muestra de inmediato para que el dueño vea qué eligió, pero
        # NO se persiste todavía — eso solo pasa al pulsar "Guardar
        # ajustes", igual que la foto en dialogo_platillo.py se previsualiza
        # antes de subirse.
        self.ruta_exportacion.value = os.path.normpath(ruta)
        self._actualizar_seguro(self.ruta_exportacion)

    # ------------------------------------------------------------------
    # Guardar ajustes
    # ------------------------------------------------------------------
    def _on_guardar_click(self, e):
        if self._ocupado:
            return
        self.router.page.run_task(self._guardar_async)

    async def _guardar_async(self):
        ruta = (self.ruta_exportacion.value or "").strip()
        if not ruta or not os.path.isdir(ruta):
            self._mostrar_error_temporal(
                "Esa carpeta ya no existe. Elige otra antes de guardar."
            )
            return

        self._ocupado = True
        self._set_boton_guardar_cargando(True)
        try:
            # guardar_ruta_exportacion() es una escritura de archivo local
            # — rápida, pero se manda a un hilo aparte de todos modos, el
            # mismo convenio que sigue todo asyncio.to_thread en este
            # proyecto para no arriesgar un frenón de disco en la UI.
            await asyncio.to_thread(guardar_ruta_exportacion, ruta)
        except OSError as e:
            print(f"[ajustes] error al guardar la ruta de exportación: {e}")
            self._mostrar_error_temporal(
                "No se pudo guardar el ajuste. Revisa los permisos de la "
                "carpeta e intenta de nuevo."
            )
            self._ocupado = False
            self._set_boton_guardar_cargando(False)
            return
        except Exception as e:
            print(f"[ajustes] error inesperado al guardar la ruta de exportación: {e}")
            traceback.print_exc()
            self._mostrar_error_temporal("No se pudo guardar el ajuste. Intenta de nuevo.")
            self._ocupado = False
            self._set_boton_guardar_cargando(False)
            return

        self._ocupado = False
        self._confirmar_guardado_visualmente()

    def _set_boton_guardar_cargando(self, cargando: bool):
        self.boton_guardar.disabled = cargando
        self.boton_guardar.content = (
            ft.Row(
                controls=[
                    ft.ProgressRing(width=16, height=16, stroke_width=2, color=C.texto),
                    ft.Text("Guardando...", color=C.texto, size=14, font_family="LetraTitulo"),
                ],
                spacing=10,
                tight=True,
            )
            if cargando
            else self._texto_boton_guardar
        )
        self._actualizar_seguro(self.boton_guardar)

    def _confirmar_guardado_visualmente(self):
        """Sin banner de éxito — el proyecto no tiene un segundo lenguaje
        visual de "aviso" además del rojo de error (ver
        dialogo_platillo.py/cloudflare_storage.py). En su lugar el propio
        botón confirma con un check verde por un momento, mismo idioma que
        ya usa biblioteca_view.py en su botón de exportar."""
        self.boton_guardar.disabled = False
        self.boton_guardar.content = ft.Row(
            controls=[
                ft.Icon(ft.Icons.CHECK, size=18, color=C.texto),
                ft.Text("Ajustes guardados", color=C.texto, size=14, font_family="LetraTitulo"),
            ],
            spacing=8,
            tight=True,
        )
        self._actualizar_seguro(self.boton_guardar)
        self.router.page.run_task(self._restaurar_boton_guardar)

    async def _restaurar_boton_guardar(self, espera_seg: float = 1.6):
        await asyncio.sleep(espera_seg)
        self.boton_guardar.content = self._texto_boton_guardar
        self._actualizar_seguro(self.boton_guardar)

    # ------------------------------------------------------------------
    # Tema
    # ------------------------------------------------------------------
    def _on_cambiar_tema(self, i: int):
        # Como en Anxie: primero se deja ver el botón del interruptor llegar
        # a su sitio y luego router.cambiar_tema() guarda la elección en
        # config.json y rehace Ajustes (con su barra) con los colores nuevos.
        nombre = TEMAS[i][2]

        async def cambiar():
            await asyncio.sleep(0.3)
            self.router.cambiar_tema(nombre)

        self.router.page.run_task(cambiar)

    # ------------------------------------------------------------------
    def _actualizar_seguro(self, *controles):
        """Si el dueño ya navegó a otra pantalla mientras una tarea en
        vuelo seguía corriendo, esta vista quedó desmontada y .update()
        lanzaría una excepción que no vería nadie — mismo patrón que
        contenido_view.py/agenteIA_view.py/biblioteca_view.py."""
        for control in controles:
            try:
                control.update()
            except Exception:
                pass

    def _mostrar_error_temporal(self, mensaje: str, duracion_seg: int = 4):
        self._banner_token += 1
        token = self._banner_token
        self.texto_error.value = mensaje
        self.zona_error.visible = True
        self._actualizar_seguro(self.zona_error)
        self.router.page.run_task(self._ocultar_banner_luego, token, duracion_seg)

    async def _ocultar_banner_luego(self, token: int, duracion_seg: int):
        await asyncio.sleep(duracion_seg)
        if token != self._banner_token:
            return
        self.zona_error.visible = False
        self._actualizar_seguro(self.zona_error)
