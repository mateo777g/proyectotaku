"""
views/sesion_view.py
Pantalla de login del panel (Fase 2.0; rediseño de layout 2026-09-05, a
pedido del dueño del código — referencia visual: una plantilla de login de
dos columnas). Ocupa toda la ventana, sin Sidebar — NO pasa por
router.cambiar_vista(), la mete directo MainController.mostrar_login().

LAYOUT DE DOS COLUMNAS:
  · Izquierda: una sección de marca/bienvenida, fondo oscuro con los MISMOS
    tokens que ya usa views/components/sidebar.py (#0d0905 de fondo, #f4ca83
    dorado, #999288 texto muted, #18120b/#2c2013 para las tarjetas) — no se
    inventó paleta nueva, se reusó la que ya existe para "superficie oscura"
    en este mismo proyecto. Incluye estadísticas reales del menú
    (PlatilloDAO.obtener_estadisticas(), mismo dato que la tarjeta
    "PRODUCTOS EN VENTA" de home_view.py), legibles sin sesión porque esa
    consulta solo cuenta visible=true, que es justo lo que anon puede leer.
  · Derecha: el formulario de acceso de siempre. El rediseño es puramente
    visual — sign_in_with_password, el candado de licencia y los mensajes
    de error NO se tocaron.

Sin sesión iniciada el panel no tiene permisos para leer ni escribir en
platillos (las políticas RLS están amarradas al UID del admin), así que esta
pantalla va antes que cualquier otra cosa.
"""
import asyncio

import flet as ft
import httpx
from supabase_auth.errors import AuthApiError

from models.configuracion_negocio_dao import ConfiguracionNegocioDAO
from models.platillo_dao import PlatilloDAO
from models.supabase_client import SUPABASE_ADMIN_EMAIL, client

# Ancho de los campos, el botón y el bloque de texto/stats del lado
# izquierdo — antes salía de "420 de tarjeta - 36 de padding a cada lado";
# ya no hay una tarjeta con borde que centrar, así que ahora es directo.
_ANCHO_CAMPO = 380
_ANCHO_PANEL_TEXTO = 440


class SesionView(ft.Container):
    def __init__(self, router):
        super().__init__()
        self.router = router
        # expand + height=inf: mismo patrón que layout_principal en
        # main_controller.py (Sidebar + content_container) — un Row de dos
        # columnas a todo lo alto de la ventana. Antes esta pantalla dejaba
        # height sin poner a propósito, porque necesitaba alignment para
        # centrar UNA tarjeta; ya no hay una sola tarjeta que centrar, hay
        # dos columnas que deben llenar la ventana completa.
        self.expand = True
        self.height = float("inf")
        self.bgcolor = "#fbf5e9"

        # ------------------------------------------------------------
        # Controles del formulario (columna derecha) — sin cambios de
        # lógica respecto a la versión anterior, solo cambia dónde viven
        # dentro del árbol de controles.
        # ------------------------------------------------------------
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
            "Entrar al panel", color="#ffffff", weight="bold", size=16
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

        formulario = ft.Container(
            width=_ANCHO_CAMPO,
            content=ft.Column(
                # tight=True: por default un Column reclama TODO el alto
                # disponible; con tight=True usa solo el mínimo que pide su
                # contenido, que es lo que necesita un bloque que se va a
                # centrar verticalmente en la mitad derecha de la pantalla.
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.START,
                spacing=0,
                controls=[
                    ft.Text(
                        "Inicia sesión",
                        size=32,
                        font_family="Georgia",
                        italic=True,
                        color="#18120d",
                    ),
                    ft.Container(height=6),
                    ft.Text(
                        "Ingresa tus datos para administrar tu menú.",
                        size=13,
                        color="#7c7267",
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

        panel_derecho = ft.Container(
            expand=True,
            height=float("inf"),
            bgcolor="#fbf5e9",
            alignment=ft.Alignment(0, 0),
            content=formulario,
        )

        # ------------------------------------------------------------
        # Columna izquierda — sección de marca/bienvenida. Los números de
        # las tarjetas de abajo arrancan en "–" y _cargar_estadisticas() (al
        # final de este __init__) los reemplaza cuando responde Supabase;
        # si esa consulta falla, se quedan en "–" — no es motivo para
        # bloquear ni ensuciar el login con un error (ver el método).
        # ------------------------------------------------------------
        self.texto_stat_platillos = ft.Text(
            "–", size=30, weight="bold", color="#f4ca83"
        )
        self.texto_stat_categorias = ft.Text(
            "–", size=30, weight="bold", color="#f4ca83"
        )

        def _tarjeta_stat(control_numero: ft.Text, etiqueta: str) -> ft.Container:
            # Mismos tokens que la tarjeta de ayuda de sidebar.py
            # (#18120b/#2c2013): es la "tarjeta sobre fondo oscuro" que ya
            # existe en este proyecto, reusada tal cual en vez de inventar
            # una nueva.
            return ft.Container(
                expand=True,
                bgcolor="#18120b",
                border=ft.border.all(1, "#2c2013"),
                border_radius=16,
                padding=ft.padding.symmetric(horizontal=18, vertical=16),
                content=ft.Column(
                    spacing=2,
                    controls=[
                        control_numero,
                        ft.Text(etiqueta, size=12, color="#999288"),
                    ],
                ),
            )

        panel_izquierdo = ft.Container(
            expand=True,
            height=float("inf"),
            bgcolor="#0d0905",
            padding=ft.padding.symmetric(horizontal=56, vertical=48),
            content=ft.Column(
                expand=True,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                horizontal_alignment=ft.CrossAxisAlignment.START,
                controls=[
                    # Lockup de marca — mismo patrón que la parte de arriba
                    # de sidebar.py (logo + nombre + eyebrow).
                    ft.Row(
                        controls=[
                            ft.CircleAvatar(
                                foreground_image_src="assets/logomonky.png",
                                radius=26,
                                bgcolor=ft.Colors.TRANSPARENT,
                            ),
                            ft.Column(
                                spacing=1,
                                controls=[
                                    ft.Text(
                                        "Taku monky",
                                        color=ft.Colors.WHITE,
                                        weight="bold",
                                        size=19,
                                        font_family="Georgia",
                                        italic=True,
                                    ),
                                    ft.Text(
                                        "PANEL DEL DUEÑO",
                                        color="#f4ca83",
                                        size=10,
                                        weight="bold",
                                    ),
                                ],
                            ),
                        ],
                        spacing=14,
                    ),
                    # Mensaje de bienvenida
                    ft.Container(
                        width=_ANCHO_PANEL_TEXTO,
                        content=ft.Column(
                            spacing=14,
                            horizontal_alignment=ft.CrossAxisAlignment.START,
                            controls=[
                                ft.Text(
                                    "Bienvenido\nde vuelta",
                                    size=44,
                                    font_family="Georgia",
                                    italic=True,
                                    color=ft.Colors.WHITE,
                                ),
                                ft.Text(
                                    "Administra tu menú, tus ventas y tus "
                                    "mesas desde un solo lugar.",
                                    size=14,
                                    color="#999288",
                                ),
                            ],
                        ),
                    ),
                    # Estadísticas reales del menú
                    ft.Container(
                        width=_ANCHO_PANEL_TEXTO,
                        content=ft.Row(
                            spacing=16,
                            controls=[
                                _tarjeta_stat(
                                    self.texto_stat_platillos, "platillos en tu menú"
                                ),
                                _tarjeta_stat(
                                    self.texto_stat_categorias, "categorías activas"
                                ),
                            ],
                        ),
                    ),
                ],
            ),
        )

        self.content = ft.Row(
            expand=True,
            height=float("inf"),
            spacing=0,
            controls=[panel_izquierdo, panel_derecho],
        )

        # Estadísticas del panel izquierdo: se piden aparte del login (no
        # requieren sesión, PlatilloDAO.obtener_estadisticas() solo cuenta
        # visible=true) — mismo patrón que home_view.py, que llama a sus
        # cargas async al final de __init__ vía page.run_task().
        self.router.page.run_task(self._cargar_estadisticas)

    async def _cargar_estadisticas(self):
        """Llena los dos números de la columna izquierda con datos reales
        del menú. Es un detalle de "bienvenida", no parte del flujo de
        login: si falla (sin internet, Supabase caído, etc.) los números se
        quedan en "–" y no se le muestra ningún error al usuario — el login
        en sí no depende de esto para nada."""
        try:
            stats = await asyncio.to_thread(PlatilloDAO.obtener_estadisticas)
        except Exception as e:
            print(f"[login] no se pudieron cargar las estadísticas del menú: {e}")
            return

        self.texto_stat_platillos.value = str(stats["total"])
        self.texto_stat_categorias.value = str(stats["categorias_en_uso"])
        self.texto_stat_platillos.update()
        self.texto_stat_categorias.update()

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

            # NO se guarda nada en disco (2026-09-05, antes aquí iba
            # sesion.guardar()): la sesión vive solo en la memoria del
            # cliente de Supabase y muere al cerrar la app, así que el panel
            # pide contraseña en CADA arranque. Ver el bloque "POR QUÉ EL
            # LOGIN NO SE GUARDA" del roadmap — es una decisión de negocio,
            # no de seguridad: es lo que hace que cortarle la licencia a un
            # local surta efecto de inmediato.

            # EL CANDADO DE LICENCIA. Va aquí, DESPUÉS del login y ANTES de
            # mostrar_panel(): leer configuracion_negocio necesita sesión
            # (anon no tiene ninguna política sobre esa tabla), así que
            # autenticar primero es obligado, no un descuido.
            if not await self._licencia_ok():
                return
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

    async def _licencia_ok(self) -> bool:
        """Revisa el interruptor de licencia del negocio (configuracion_
        negocio.activo). Si no está activo —o si no se pudo averiguar—
        cierra la sesión recién abierta y deja al usuario en el login.

        POR QUÉ EXISTE: este software se renta por semestre. Cuando se
        acaba el pago, la idea es justamente esta: que ya no puedan entrar
        ni al panel ni a mesas.html, y solo les quede la página pública del
        menú, que sola no les sirve. Ver el bloque "POR QUÉ EL LOGIN NO SE
        GUARDA" del roadmap.

        SI NO SE PUDO AVERIGUAR, NO DEJA PASAR. No es paranoia: si dejara
        pasar ante un error, saltarse el candado sería tan fácil como
        tumbar esa consulta. Y no le quita nada al cliente legítimo — si
        Supabase no contesta, el panel no sirve igual, porque el menú, las
        ventas y las mesas viven ahí.
        """
        try:
            activa = await asyncio.to_thread(ConfiguracionNegocioDAO.licencia_activa)
        except Exception as e:
            print(f"[licencia] no se pudo verificar la licencia: {e}")
            await self._cerrar_sesion_silenciosa()
            self._mostrar_error(
                "No se pudo verificar la licencia. Revisa tu internet e "
                "intenta de nuevo."
            )
            self._set_cargando(False)
            return False

        if not activa:
            print("[licencia] activo = False: se bloquea la entrada al panel.")
            await self._cerrar_sesion_silenciosa()
            self._mostrar_error(
                "Este sistema está desactivado. Comunícate con el proveedor "
                "del software para reactivarlo."
            )
            self._set_cargando(False)
            return False

        return True

    async def _cerrar_sesion_silenciosa(self):
        """Tira la sesión que se acaba de abrir, para que no quede viva en
        `client.auth` después de un rechazo. Si el sign_out falla da igual:
        la sesión no se guarda en ningún lado y muere al cerrar la app."""
        try:
            await asyncio.to_thread(client.auth.sign_out)
        except Exception as e:
            print(f"[licencia] sign_out tras el rechazo falló, se ignora: {e}")

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
