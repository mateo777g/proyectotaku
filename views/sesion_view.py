"""
views/sesion_view.py
Pantalla de login del panel (Fase 2.0). Ocupa toda la ventana, sin Sidebar
— NO pasa por router.cambiar_vista(), la mete directo MainController.mostrar_login().

Sin sesión iniciada el panel no tiene permisos para leer ni escribir en
platillos (las políticas RLS están amarradas al UID del admin), así que esta
pantalla va antes que cualquier otra cosa.
"""
import asyncio

import flet as ft
import httpx
from supabase_auth.errors import AuthApiError

from models import sesion
from models.supabase_client import SUPABASE_ADMIN_EMAIL, client

# Ancho útil dentro de la tarjeta (420 de ancho total, 36px de padding a
# cada lado) — todos los campos y el botón lo comparten para verse alineados.
_ANCHO_CAMPO = 420 - 36 - 36


class SesionView(ft.Container):
    def __init__(self, router):
        super().__init__()
        self.router = router
        # Sin height=float("inf") a propósito: a diferencia de las demás
        # vistas (dentro de un Row/Column ya expandido), esta pantalla se
        # agrega directo a la page y necesita una altura real resuelta para
        # que alignment centre la tarjeta de verdad.
        self.expand = True
        self.bgcolor = "#fbf5e9"
        self.alignment = ft.Alignment(0, 0)

        self.campo_correo = ft.TextField(
            value=SUPABASE_ADMIN_EMAIL,
            hint_text="Tu correo",
            prefix_icon=ft.Icons.MAIL_OUTLINE,
            keyboard_type=ft.KeyboardType.EMAIL,
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
        )

        self.campo_password = ft.TextField(
            hint_text="Tu contraseña",
            prefix_icon=ft.Icons.LOCK_OUTLINE,
            password=True,
            can_reveal_password=True,
            width=_ANCHO_CAMPO,
            height=52,
            border_radius=16,
            border_color="#eadfca",
            focused_border_color="#f4ca83",
            bgcolor="#f8f1de",
            color="#5e5449",
            hint_style=ft.TextStyle(color="#9b8f7e"),
            text_size=14,
            on_submit=self._on_entrar_click,
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

        # Contenido normal del botón; se guarda aparte para poder volver a
        # ponerlo cuando termina de validar (ver _set_cargando).
        self._contenido_boton = ft.Text(
            "Entrar", color="#ffffff", weight="bold", size=16
        )
        self.boton_entrar = ft.Container(
            content=self._contenido_boton,
            alignment=ft.Alignment(0, 0),
            bgcolor="#0d0905",
            border_radius=30,
            width=_ANCHO_CAMPO,
            padding=ft.padding.symmetric(vertical=16),
            ink=True,
            on_click=self._on_entrar_click,
        )

        tarjeta = ft.Container(
            width=420,
            bgcolor="#f8f1de",
            border=ft.border.all(1, "#eadfca"),
            border_radius=16,
            padding=ft.padding.symmetric(horizontal=36, vertical=40),
            shadow=ft.BoxShadow(
                blur_radius=12,
                color=ft.Colors.with_opacity(0.28, ft.Colors.BLACK),
                offset=ft.Offset(0, 4),
            ),
            content=ft.Column(
                # tight=True: por default un Column reclama TODO el alto
                # disponible (así estira a `tarjeta` con él); con tight=True
                # usa solo el mínimo que pide su contenido, que es lo que
                # necesita una tarjeta que se va a centrar en la pantalla.
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=0,
                controls=[
                    ft.CircleAvatar(
                        foreground_image_src="assets/logomonky.png",
                        radius=34,
                        bgcolor=ft.Colors.TRANSPARENT,
                    ),
                    ft.Container(height=18),
                    ft.Text(
                        "PANEL DEL DUEÑO",
                        size=11,
                        weight="bold",
                        color="#b58a6d",
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        "Taku monky",
                        size=40,
                        font_family="Georgia",
                        italic=True,
                        color="#18120d",
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=6),
                    ft.Text(
                        "Inicia sesión para administrar tu menú.",
                        size=13,
                        color="#7c7267",
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=28),
                    self.campo_correo,
                    ft.Container(height=14),
                    self.campo_password,
                    self.zona_error,
                    ft.Container(height=24),
                    self.boton_entrar,
                ],
            ),
        )

        self.content = tarjeta

    def _on_entrar_click(self, e):
        self.router.page.run_task(self._iniciar_sesion)

    async def _iniciar_sesion(self):
        correo = (self.campo_correo.value or "").strip()
        password = self.campo_password.value or ""

        if not correo or not password:
            self._mostrar_error("Correo o contraseña incorrectos.")
            return

        self._set_cargando(True)
        try:
            # sign_in_with_password es una llamada de red bloqueante (SDK
            # sync) — se manda a un hilo aparte para no congelar la ventana.
            respuesta = await asyncio.to_thread(
                client.auth.sign_in_with_password,
                {"email": correo, "password": password},
            )
            if not respuesta.session:
                self._mostrar_error("Correo o contraseña incorrectos.")
                self._set_cargando(False)
                return

            sesion.guardar(respuesta.session)
            self.router.mostrar_panel()
            return  # la vista ya se reemplazó; no tocar más sus controles
        except AuthApiError as e:
            print(f"[login] credenciales rechazadas: {e}")
            self._mostrar_error("Correo o contraseña incorrectos.")
        except httpx.RequestError as e:
            print(f"[login] error de red: {e}")
            self._mostrar_error(
                "No hay conexión con el servidor. Revisa tu internet."
            )
        except Exception as e:
            print(f"[login] error inesperado: {e}")
            self._mostrar_error("Algo salió mal al iniciar sesión. Intenta de nuevo.")

        self._set_cargando(False)

    def _mostrar_error(self, mensaje: str):
        self.texto_error.value = mensaje
        self.zona_error.visible = True
        self.zona_error.update()

    def _set_cargando(self, cargando: bool):
        self.boton_entrar.disabled = cargando
        self.boton_entrar.content = (
            ft.ProgressRing(width=18, height=18, stroke_width=2, color="#f4ca83")
            if cargando
            else self._contenido_boton
        )
        self.boton_entrar.update()
