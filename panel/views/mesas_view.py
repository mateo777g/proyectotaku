"""
views/mesas_view.py
Pantalla del panel para administrar el catálogo de mesas (Fase 5.1) — el
dueño agrega/renombra/borra mesas aquí, y esa misma lista (tabla
public.mesas) es la que mesas.html usa para mostrar "Mesa 1: disponible",
"Mesa 2: ocupada, $340, hace 12 min", etc.

Mismo patrón de página que menu_view.py, recortado: sin buscador y sin
columnas de categoría/precio/foto — una mesa solo tiene un nombre. Pintada
con el diseño oscuro del panel (views/tema.py + views/piezas.py).
"""
import asyncio

import flet as ft
import httpx

from models.mesa_dao import MesaDAO
from views.components.dialogo_mesa import DialogoMesa
from views.components.dialogo_platillo import _confirmar
from views.piezas import (aviso, boton_atajo, boton_icono, fondo_pagina, tarjeta_iphone, texto,
                          titulo_vista)
from views.tema import C


class MesasView(ft.Container):
    def __init__(self, router):
        super().__init__()
        self.router = router
        self.expand = True
        self.bgcolor = C.fondo
        self.gradient = fondo_pagina()
        self.padding = 40

        self._mesas: list[dict] = []

        self.texto_titulo = titulo_vista("Cargando tus mesas...")

        self.cuerpo_lista = ft.Column(
            spacing=0,
            controls=self._estado_cargando(),
        )

        self.content = ft.Column(
            expand=True,
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.Row(
                    controls=[
                        ft.Column(
                            expand=True,
                            spacing=2,
                            controls=[
                                texto("MESAS", 14),
                                self.texto_titulo,
                            ],
                        ),
                        boton_atajo(ft.Icons.ADD, "Agregar mesa", self._on_agregar_click, ancho=200),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(height=8),
                texto("Estas son las mesas que aparecen para elegir en mesas.html — "
                      "el sistema de registro de ventas.", 13, suave=True),
                ft.Container(height=25),
                ft.Row([tarjeta_iphone(self.cuerpo_lista)]),
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
        titulo = "1 mesa" if len(self._mesas) == 1 else f"{len(self._mesas)} mesas"
        self._mostrar_estado(filas, titulo)

    def _mostrar_estado(self, controles: list, texto_titulo: str):
        self.cuerpo_lista.controls = controles
        self.texto_titulo.value = texto_titulo
        try:
            self.cuerpo_lista.update()
            self.texto_titulo.update()
        except RuntimeError:
            pass    # se salió de la vista antes de que llegaran los datos

    def _estado_cargando(self):
        return [self._caja_centrada("Cargando tus mesas...", "Un momento…")]

    def _estado_vacio(self):
        return [self._caja_centrada("Todavía no hay ninguna mesa.",
                                    "Agrega la primera con el botón de arriba.")]

    def _estado_error(self):
        return [self._caja_centrada("Sin conexión.",
                                    "No hay conexión con el servidor. Revisa tu internet.")]

    def _caja_centrada(self, titulo: str, subtitulo: str | None = None):
        controles = [texto(titulo, 14)]
        if subtitulo:
            controles.append(texto(subtitulo, 12, suave=True))
        return ft.Container(
            padding=ft.Padding.symmetric(vertical=40),
            alignment=ft.Alignment(0, 0),
            content=ft.Column(
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=6,
                controls=controles,
            ),
        )

    # ------------------------------------------------------------------
    def _crear_fila(self, mesa: dict):
        return ft.Container(
            height=60,
            border=ft.Border.only(bottom=ft.BorderSide(1, C.linea)),
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.TABLE_RESTAURANT_OUTLINED, color=C.texto_suave, size=20),
                    texto(mesa.get("nombre") or "", 14, titulo=True, expand=True,
                          max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Row(
                        controls=[
                            boton_icono(ft.Icons.EDIT_OUTLINED,
                                        lambda e, m=mesa: self._on_editar_click(m),
                                        "Renombrar mesa"),
                            boton_icono(ft.Icons.DELETE_OUTLINE,
                                        lambda e, m=mesa: self._on_eliminar_click(m),
                                        "Eliminar mesa"),
                        ],
                        spacing=8,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
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

    def _mostrar_error_temporal(self, mensaje: str):
        aviso(self.router.page, mensaje)

    def _on_guardado(self):
        self.router.page.run_task(self._cargar_mesas)
