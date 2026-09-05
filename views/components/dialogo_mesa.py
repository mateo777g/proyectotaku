"""
views/components/dialogo_mesa.py
Diálogo de alta/edición de una mesa (Fase 5.1) — se abre desde "Agregar
mesa" y el lápiz de cada fila en views/mesas_view.py.

Versión reducida de views/components/dialogo_platillo.py: una sola mesa
solo tiene `nombre`, así que este diálogo es un único TextField en vez de
foto+nombre+descripción+categoría+precio. Mismo lenguaje visual de todos
modos (tarjeta 420, campos height=52/border_radius=16, botón oscuro
border_radius=30, misma caja de error roja) y el mismo gotcha de Flet
(Column con tight=True) — no hay razón para inventar un estilo nuevo solo
porque el formulario es más chico.

El botón "X" explícito + el guard `_ocupado` en `_cerrar()` existen por la
MISMA razón documentada en dialogo_platillo.py: AlertDialog(modal=True) no
deja cancelar con tap-fuera ni Escape en esta versión de Flet, y sin el
guard un guardado a medias se podría cortar a la mitad.
"""
import asyncio

import flet as ft
import httpx

from models.mesa_dao import MesaDAO

_ANCHO_TARJETA = 420
_ANCHO_CAMPO = _ANCHO_TARJETA - 36 - 36


class DialogoMesa:
    """Uso: DialogoMesa(router, on_guardado=callback, mesa=fila_o_None).abrir()

    `mesa=None` → modo alta. `mesa=<dict>` → modo edición, precargado con
    esa fila. `on_guardado` se llama tras crear/actualizar con éxito para
    que mesas_view.py refresque la lista — sin argumentos (a diferencia de
    DialogoPlatillo, aquí no hay ninguna limpieza de Cloudflare de la que
    avisar)."""

    def __init__(self, router, on_guardado, mesa: dict | None = None):
        self.router = router
        self.page = router.page
        self.on_guardado = on_guardado
        self.editando = mesa is not None
        self.mesa = mesa or {}
        self._ocupado = False

        self.campo_nombre = ft.TextField(
            value=self.mesa.get("nombre", ""),
            hint_text='Ej. "Mesa 6" o "Barra 1"',
            prefix_icon=ft.Icons.TABLE_RESTAURANT_OUTLINED,
            autofocus=True,
            width=_ANCHO_CAMPO,
            height=52,
            border_radius=16,
            border_color="#eadfca",
            focused_border_color="#f4ca83",
            bgcolor="#f8f1de",
            color="#5e5449",
            hint_style=ft.TextStyle(color="#9b8f7e"),
            text_size=14,
            on_submit=self._on_guardar_click,
        )

        self.texto_error = ft.Text("", size=12, color="#a33c39", expand=True)
        self.zona_error = ft.Container(
            visible=False,
            width=_ANCHO_CAMPO,
            bgcolor="#f7e4e3",
            border=ft.border.all(1, "#d9534f"),
            border_radius=12,
            padding=ft.padding.symmetric(horizontal=12, vertical=10),
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE, size=15, color="#d9534f"),
                    self.texto_error,
                ],
                spacing=8,
            ),
        )

        self._texto_boton_guardar = ft.Text(
            "Guardar cambios" if self.editando else "Agregar mesa",
            color="#ffffff",
            weight="bold",
            size=16,
        )
        self.boton_guardar = ft.Container(
            content=self._texto_boton_guardar,
            alignment=ft.Alignment(0, 0),
            bgcolor="#0d0905",
            border_radius=30,
            width=_ANCHO_CAMPO,
            padding=ft.padding.symmetric(vertical=16),
            ink=True,
            on_click=self._on_guardar_click,
        )

        self.boton_cerrar = ft.Container(
            content=ft.Icon(ft.Icons.CLOSE, size=16, color="#756b5e"),
            width=30,
            height=30,
            border_radius=15,
            ink=True,
            alignment=ft.Alignment(0, 0),
            on_click=lambda e: self._cerrar(),
            top=12,
            right=12,
            tooltip="Cerrar",
        )

        self.dialog = ft.AlertDialog(
            modal=True,
            bgcolor="#f8f1de",
            shape=ft.RoundedRectangleBorder(radius=16),
            content_padding=ft.padding.symmetric(horizontal=36, vertical=36),
            content=ft.Stack(
                controls=[
                    ft.Container(
                        width=_ANCHO_TARJETA - 72,
                        content=ft.Column(
                            tight=True,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=0,
                            controls=[
                                ft.Text(
                                    "EDITAR MESA" if self.editando else "AGREGAR MESA",
                                    size=11,
                                    weight="bold",
                                    color="#b58a6d",
                                    text_align=ft.TextAlign.CENTER,
                                ),
                                ft.Text(
                                    self.mesa.get("nombre") if self.editando else "Nueva mesa",
                                    size=26,
                                    font_family="Georgia",
                                    italic=True,
                                    color="#18120d",
                                    text_align=ft.TextAlign.CENTER,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Container(height=24),
                                self.campo_nombre,
                                self.zona_error,
                                ft.Container(height=22),
                                self.boton_guardar,
                            ],
                        ),
                    ),
                    self.boton_cerrar,
                ],
            ),
        )

    # ------------------------------------------------------------------
    def abrir(self):
        self.page.show_dialog(self.dialog)

    def _cerrar(self):
        if self._ocupado:
            return
        self.page.pop_dialog()

    def _validar(self):
        nombre = (self.campo_nombre.value or "").strip()
        if not nombre:
            return None, "Escribe un nombre para la mesa."
        return nombre, None

    def _on_guardar_click(self, e):
        nombre, error = self._validar()
        if error:
            self._mostrar_error(error)
            return
        self.page.run_task(self._guardar, nombre)

    async def _guardar(self, nombre: str):
        self._set_cargando(True)
        try:
            if self.editando:
                await asyncio.to_thread(MesaDAO.actualizar, self.mesa["id"], nombre)
            else:
                await asyncio.to_thread(MesaDAO.crear, nombre)
        except httpx.RequestError as e:
            print(f"[dialogo_mesa] error de red al guardar: {e}")
            self._mostrar_error("No hay conexión con el servidor. Revisa tu internet.")
            self._set_cargando(False)
            return
        except Exception as e:
            # Incluye el choque con la restricción UNIQUE(nombre) si ya
            # existe una mesa con ese nombre — Postgres lo rechaza con un
            # error de la API que cae aquí, no hace falta un chequeo aparte.
            print(f"[dialogo_mesa] error al guardar: {e}")
            self._mostrar_error("No se pudo guardar. ¿Ya existe una mesa con ese nombre?")
            self._set_cargando(False)
            return

        self._set_cargando(False)  # si no, _cerrar() se niega a cerrar (_ocupado sigue True)
        self._cerrar()
        self.on_guardado()

    def _mostrar_error(self, mensaje: str):
        self.texto_error.value = mensaje
        self.zona_error.visible = True
        self.zona_error.update()

    def _set_cargando(self, cargando: bool):
        self._ocupado = cargando
        self.boton_guardar.disabled = cargando
        self.boton_guardar.content = (
            ft.Row(
                controls=[
                    ft.ProgressRing(width=18, height=18, stroke_width=2, color="#f4ca83"),
                    ft.Text("Guardando...", color="#ffffff", weight="bold", size=14),
                ],
                spacing=10,
                alignment=ft.MainAxisAlignment.CENTER,
            )
            if cargando
            else self._texto_boton_guardar
        )
        self.boton_guardar.update()
