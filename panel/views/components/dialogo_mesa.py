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
from views.piezas import (apagar_boton, boton_atajo, boton_cerrar_dialogo, caja_error, campo,
                          dialogo_tarjeta, texto)

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

        self.campo_nombre = campo(
            valor=self.mesa.get("nombre", ""),
            pista='Ej. "Mesa 6" o "Barra 1"',
            icono=ft.Icons.TABLE_RESTAURANT_OUTLINED,
            tamano=13,
            autofoco=True,
            al_enviar=self._on_guardar_click,
        )

        self.texto_error = texto("", 12, expand=True)
        self.zona_error = caja_error(self.texto_error)

        self.boton_guardar = boton_atajo(
            ft.Icons.CHECK if self.editando else ft.Icons.ADD,
            "Guardar cambios" if self.editando else "Agregar mesa",
            self._on_guardar_click,
        )

        self.dialog = dialogo_tarjeta(
            ft.Column(
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=0,
                controls=[
                    texto("EDITAR MESA" if self.editando else "AGREGAR MESA", 12, suave=True,
                          text_align=ft.TextAlign.CENTER),
                    ft.Container(height=4),
                    texto(self.mesa.get("nombre") if self.editando else "Nueva mesa", 26,
                          titulo=True, text_align=ft.TextAlign.CENTER, max_lines=1,
                          overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Container(height=24),
                    ft.Row([self.campo_nombre]),
                    self.zona_error,
                    ft.Container(height=22),
                    ft.Row([self.boton_guardar]),
                ],
            ),
            _ANCHO_TARJETA,
            boton_cerrar_dialogo(lambda e: self._cerrar()),
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
        # Apagado mientras guarda (sin rueda de carga: el apagado ya lo dice).
        self._ocupado = cargando
        apagar_boton(self.boton_guardar, cargando)
        self.boton_guardar.update()
