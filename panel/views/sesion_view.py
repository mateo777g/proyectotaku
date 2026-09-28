"""
views/sesion_view.py
La pantalla de entrar del panel, con el diseño oscuro de la guía (A4.7). Ocupa toda la ventana,
sin barra lateral, y siempre es lo primero al abrir: la sesión NUNCA se guarda en disco
(decisión de negocio, ver "POR QUÉ EL LOGIN NO SE GUARDA" del roadmap).

Dos mitades del mismo alto: a la izquierda una tarjeta con correo + contraseña y a la derecha
las manchas azules con grano, la frase y la etiqueta de la marca.

Lo que NO cambió con el rediseño: sign_in_with_password, el candado de licencia justo después
del login (fail closed) y los mensajes. Los errores salen como aviso (la píldora de piezas.py).
"""
import asyncio

import flet as ft
import httpx
from supabase_auth.errors import AuthApiError

from models.configuracion_negocio_dao import ConfiguracionNegocioDAO
from models.supabase_client import SUPABASE_ADMIN_EMAIL, client
from views.piezas import apagar_boton, aviso, boton_atajo, campo, sin_auto_update, tarjeta_iphone
from views.tema import C

# Todo a 48 del borde de su mitad, 56 arriba: el título de la tarjeta y la frase de las manchas
# empiezan a la misma altura y a la misma distancia de su borde.
MARGEN, MARGEN_ARRIBA = 48, 56
RADIO = 16
# Los campos: 56 de alto (relleno 18 arriba y abajo).
RELLENO_CAMPO = ft.Padding(left=12, top=18, right=12, bottom=18)


def encabezado(titulo, subtitulo):
    return [
        ft.Text(titulo, size=56, color=C.texto, font_family="LetraTitulo",
                style=ft.TextStyle(height=1.0)),
        ft.Container(height=14),
        ft.Text(subtitulo, size=22, color=C.texto_suave, font_family="LetraTexto"),
    ]


class SesionView(ft.Container):
    def __init__(self, router):
        super().__init__()
        self.router = router
        self.page_ref = router.page
        self.expand = True
        # Liso, sin degradado: que solo brillen las manchas.
        self.bgcolor = C.fondo_entrar
        self.padding = 12

        self.campo_correo = campo(pista="Tu correo", icono=ft.Icons.MAIL_OUTLINE, tamano=15,
                                  valor=SUPABASE_ADMIN_EMAIL, relleno=RELLENO_CAMPO)
        self.campo_correo.keyboard_type = ft.KeyboardType.EMAIL
        # El correo ya viene puesto (el del .env): el foco empieza en la contraseña.
        self.campo_password = campo(pista="Tu contraseña", icono=ft.Icons.LOCK_OUTLINE,
                                    contrasena=True, tamano=15, autofoco=True,
                                    relleno=RELLENO_CAMPO,
                                    al_enviar=sin_auto_update(self._on_entrar_click))
        # "Entrar", el único botón destacado del panel: la forma de los campos, en blanco.
        self.boton_entrar = boton_atajo(ft.Icons.LOGIN, "Entrar al panel", self._on_entrar_click,
                                        claro=True, alto=51, radio=10)

        tarjeta = tarjeta_iphone(
            ft.Column([
                *encabezado("Inicia sesión", "Ingresa tus datos para administrar tu menú."),
                ft.Container(height=48),
                ft.Row([self.campo_correo]),
                ft.Container(height=12),
                ft.Row([self.campo_password]),
                ft.Container(height=16),
                ft.Row([self.boton_entrar]),
            ], spacing=0),
            radio=RADIO, expand=94, colores=C.tarjeta_entrar,
            padding=ft.Padding(left=MARGEN - 1, top=MARGEN_ARRIBA - 1, right=MARGEN - 1, bottom=MARGEN - 1))

        # A la derecha, las manchas azules con grano (WebP animado: Flutter lo reproduce solo),
        # la frase y la etiqueta de la marca. Oscuras en los dos temas.
        grano = ft.Container(
            expand=106, border_radius=RADIO, bgcolor="#000000", border=ft.Border.all(1, "#1FFFFFFF"),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=ft.Stack([
                ft.Image(src="assets/login-grano.webp", fit=ft.BoxFit.COVER,
                         width=float("inf"), height=float("inf")),
                ft.Container(left=MARGEN, top=MARGEN_ARRIBA, content=ft.Text(
                    "Moderniza\nTu Negocio", size=56, color=ft.Colors.WHITE,
                    font_family="LetraTitulo", style=ft.TextStyle(height=1.0))),
                ft.Container(left=MARGEN, right=MARGEN, bottom=MARGEN, content=etiqueta_marca()),
            ]))
        self.content = ft.Row([tarjeta, grano], spacing=12,
                              vertical_alignment=ft.CrossAxisAlignment.STRETCH)

    def _on_entrar_click(self, e):
        self.page_ref.run_task(self._iniciar_sesion)

    async def _iniciar_sesion(self):
        if self.boton_entrar.disabled:
            return
        correo = (self.campo_correo.value or "").strip()
        password = self.campo_password.value or ""

        if not correo or not password:
            self._mostrar_error("Correo o contraseña incorrectos.")
            return

        self._set_cargando(True)
        try:
            # sign_in_with_password es red bloqueante (SDK sync): a un hilo aparte.
            respuesta = await asyncio.to_thread(
                client.auth.sign_in_with_password,
                {"email": correo, "password": password},
            )
            if not respuesta.session:
                self._mostrar_error("Correo o contraseña incorrectos.")
                self._set_cargando(False)
                return

            # EL CANDADO DE LICENCIA: después del login y antes de entrar.
            if not await self._licencia_ok():
                return
            self.router.mostrar_panel()
            return  # la vista ya se reemplazó; no tocar más sus controles
        except AuthApiError as e:
            print(f"[login] credenciales rechazadas: {e}")
            self._mostrar_error("Correo o contraseña incorrectos.")
        except httpx.RequestError as e:
            print(f"[login] error de red: {e}")
            self._mostrar_error("No hay conexión con el servidor. Revisa tu internet.")
        except Exception as e:
            print(f"[login] error inesperado: {e}")
            self._mostrar_error("Algo salió mal al iniciar sesión. Intenta de nuevo.")

        self._set_cargando(False)

    async def _licencia_ok(self) -> bool:
        """Revisa configuracion_negocio.activo. Si no está activo —o si no se pudo averiguar—
        cierra la sesión recién abierta y se queda aquí. Si no se pudo averiguar, NO deja pasar."""
        try:
            activa = await asyncio.to_thread(ConfiguracionNegocioDAO.licencia_activa)
        except Exception as e:
            print(f"[licencia] no se pudo verificar la licencia: {e}")
            await self._cerrar_sesion_silenciosa()
            self._mostrar_error("No se pudo verificar la licencia. Revisa tu internet e intenta de nuevo.")
            self._set_cargando(False)
            return False

        if not activa:
            print("[licencia] activo = False: se bloquea la entrada al panel.")
            await self._cerrar_sesion_silenciosa()
            self._mostrar_error("Este sistema está desactivado. Comunícate con el proveedor "
                                "del software para reactivarlo.")
            self._set_cargando(False)
            return False

        return True

    async def _cerrar_sesion_silenciosa(self):
        try:
            await asyncio.to_thread(client.auth.sign_out, {"scope": "local"})
        except Exception as e:
            print(f"[licencia] sign_out tras el rechazo falló, se ignora: {e}")

    def _mostrar_error(self, mensaje: str):
        aviso(self.page_ref, mensaje, barra=0)

    def _set_cargando(self, cargando: bool):
        # Apagado mientras entra: no hay rueda de carga, el apagado ya lo dice.
        apagar_boton(self.boton_entrar, cargando)
        self.boton_entrar.update()


def etiqueta_marca():
    # La etiqueta de abajo de las manchas: translúcida, borde parejo, el logo en blanco y
    # "Fragmentless · Panel de escritorio" al 85 %. No se pulsa.
    fila = ft.Row([
        ft.Image(src="assets/fragmentless-blanco.png", height=22, fit=ft.BoxFit.CONTAIN),
        ft.Text("Fragmentless · Panel de escritorio", size=15, color=ft.Colors.WHITE, font_family="LetraTitulo"),
    ], spacing=10, tight=True, opacity=0.85)
    return ft.Container(height=48, border_radius=10, bgcolor="#0DFFFFFF", blur=ft.Blur(8, 8),
                        border=ft.Border.all(1, "#40FFFFFF"), alignment=ft.Alignment.CENTER_LEFT,
                        padding=ft.Padding(left=18, top=0, right=22, bottom=0), content=fila)
