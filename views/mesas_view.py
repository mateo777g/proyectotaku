"""
views/mesas_view.py
Pantalla del panel para administrar el catálogo de mesas (Fase 5.1) — el
dueño agrega/renombra/borra mesas aquí, y esa misma lista (tabla
public.mesas) es la que mesas.html usa para mostrar "Mesa 1: disponible",
"Mesa 2: ocupada, $340, hace 12 min", etc. en vez del campo de texto libre
que tenía antes.

Mismo patrón de página que menu_view.py, recortado: sin buscador (una
lista de mesas es corta, no hace falta filtrarla) y sin columnas de
categoría/precio/foto — una mesa solo tiene un nombre. El diálogo de alta/
edición (views/components/dialogo_mesa.py) y la confirmación de borrado
(_confirmar, reusada tal cual de dialogo_platillo.py en vez de duplicarla)
sí siguen el mismo lenguaje visual que el resto del panel.
"""
import asyncio

import flet as ft
import httpx

from models.mesa_dao import MesaDAO
from views.components.dialogo_mesa import DialogoMesa
from views.components.dialogo_platillo import _confirmar


class MesasView(ft.Container):
    def __init__(self, router):
        super().__init__()
        self.router = router
        self.expand = True
        self.height = float("inf")
        self.bgcolor = "#fbf5e9"
        self.padding = ft.padding.only(left=36, right=36, top=42, bottom=36)

        self._mesas: list[dict] = []
        self._banner_token = 0

        # Banner temporal para el error de eliminar (no tiene diálogo propio
        # donde mostrarlo, a diferencia de agregar/editar) — mismo patrón
        # que menu_view.py._mostrar_error_temporal().
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

        self.texto_titulo = ft.Text(
            "Cargando tus mesas...",
            size=40,
            font_family="Georgia",
            italic=True,
            color="#18120d",
        )

        self.cuerpo_lista = ft.Column(
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
                                ft.Text("MESAS", size=13, weight="bold", color="#b58a6d"),
                                self.texto_titulo,
                            ],
                        ),
                        ft.Container(
                            content=ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.ADD, color="#ffa200", size=22),
                                    ft.Text("Agregar mesa", color="#ffffff", weight="bold", size=16),
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
                ft.Container(height=8),
                ft.Text(
                    "Estas son las mesas que aparecen para elegir en mesas.html — "
                    "el sistema de registro de ventas.",
                    size=13,
                    color="#7c7267",
                ),
                ft.Container(height=18),
                self.banner_error,
                ft.Container(height=6),
                self.cuerpo_lista,
            ],
        )

        self.router.page.run_task(self._cargar_mesas)

    # ------------------------------------------------------------------
    async def _cargar_mesas(self):
        try:
            self._mesas = await asyncio.to_thread(MesaDAO.obtener_todos)
        except httpx.RequestError as e:
            print(f"[mesas] error de red al traer mesas: {e}")
            self._mostrar_estado(self._estado_error(), "Tus mesas")
            return
        except Exception as e:
            print(f"[mesas] error inesperado al traer mesas: {e}")
            self._mostrar_estado(self._estado_error(), "Tus mesas")
            return

        if not self._mesas:
            self._mostrar_estado(self._estado_vacio(), "0 mesas")
            return

        filas = [self._crear_fila(m) for m in self._mesas]
        texto = "1 mesa" if len(self._mesas) == 1 else f"{len(self._mesas)} mesas"
        self._mostrar_estado(filas, texto)

    def _mostrar_estado(self, controles: list, texto_titulo: str):
        self.cuerpo_lista.controls = controles
        self.texto_titulo.value = texto_titulo
        self.cuerpo_lista.update()
        self.texto_titulo.update()

    def _estado_cargando(self):
        return [self._caja_centrada(ft.ProgressRing(width=28, height=28, stroke_width=3, color="#f4ca83"), "Cargando tus mesas...")]

    def _estado_vacio(self):
        return [
            self._caja_centrada(
                ft.Icon(ft.Icons.TABLE_RESTAURANT_OUTLINED, size=30, color="#c9bda3"),
                "Todavía no hay ninguna mesa.",
                "Agrega la primera con el botón de arriba.",
            )
        ]

    def _estado_error(self):
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

    def _caja_centrada(self, icono_o_spinner, titulo: str, subtitulo: str | None = None):
        controles = [icono_o_spinner, ft.Text(titulo, size=14, weight="bold", color="#5e5449")]
        if subtitulo:
            controles.append(ft.Text(subtitulo, size=12, color="#8a7e72"))
        return ft.Container(
            bgcolor="#f8f1de",
            border_radius=14,
            padding=ft.padding.symmetric(vertical=48),
            alignment=ft.Alignment(0, 0),
            content=ft.Column(
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
                controls=controles,
            ),
        )

    # ------------------------------------------------------------------
    def _crear_fila(self, mesa: dict):
        return ft.Container(
            bgcolor="#f8f1de",
            padding=ft.padding.symmetric(horizontal=18, vertical=14),
            border=ft.border.only(bottom=ft.BorderSide(1, "#eadfca")),
            content=ft.Row(
                controls=[
                    ft.Text(
                        mesa.get("nombre") or "",
                        size=15,
                        font_family="Georgia",
                        italic=True,
                        weight="bold",
                        color="#1c1610",
                        expand=True,
                    ),
                    ft.Row(
                        controls=[
                            self._accion(
                                ft.Icons.EDIT_OUTLINED,
                                on_click=lambda e, m=mesa: self._on_editar_click(m),
                                tooltip="Renombrar mesa",
                            ),
                            self._accion(
                                ft.Icons.DELETE_OUTLINE,
                                on_click=lambda e, m=mesa: self._on_eliminar_click(m),
                                tooltip="Eliminar mesa",
                            ),
                        ],
                        spacing=4,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
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
    def _on_agregar_click(self, e):
        DialogoMesa(self.router, on_guardado=self._on_guardado, mesa=None).abrir()

    def _on_editar_click(self, mesa: dict):
        DialogoMesa(self.router, on_guardado=self._on_guardado, mesa=mesa).abrir()

    def _on_eliminar_click(self, mesa: dict):
        _confirmar(
            self.router.page,
            titulo="¿Eliminar esta mesa?",
            mensaje=(
                f"\"{mesa.get('nombre', '')}\" ya no aparecerá para elegir en "
                "mesas.html. Las ventas que ya se hicieron con ese nombre no "
                "se ven afectadas — se quedan tal cual en el historial."
            ),
            on_confirmar=lambda: self.router.page.run_task(self._eliminar_async, mesa),
        )

    async def _eliminar_async(self, mesa: dict):
        try:
            await asyncio.to_thread(MesaDAO.eliminar, mesa["id"])
        except httpx.RequestError as e:
            print(f"[mesas] error de red al eliminar: {e}")
            self._mostrar_error_temporal("No hay conexión con el servidor. Revisa tu internet.")
            return
        except Exception as e:
            print(f"[mesas] error al eliminar: {e}")
            self._mostrar_error_temporal("No se pudo eliminar la mesa. Intenta de nuevo.")
            return
        self.router.page.run_task(self._cargar_mesas)

    def _mostrar_error_temporal(self, mensaje: str, duracion_seg: int = 4):
        self._banner_token += 1
        token = self._banner_token
        self.texto_banner_error.value = mensaje
        self.banner_error.visible = True
        self.banner_error.update()
        self.router.page.run_task(self._ocultar_banner_luego, token, duracion_seg)

    async def _ocultar_banner_luego(self, token: int, duracion_seg: int):
        await asyncio.sleep(duracion_seg)
        if token != self._banner_token:
            return
        self.banner_error.visible = False
        self.banner_error.update()

    def _on_guardado(self):
        self.router.page.run_task(self._cargar_mesas)
