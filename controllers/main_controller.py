import flet as ft
import asyncio
from views.home_view import HomeView
from views.menu_view import MenuView
from views.mesas_view import MesasView
from views.agenteIA_view import AgenteIAView
from views.contenido_view import ContenidoView
from views.ajustes_view import AjustesView
from views.biblioteca_view import BibliotecaView
from views.components.sidebar import Sidebar
from views.sesion_view import SesionView
from models.supabase_client import client

class MainController:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Taku Monky - Panel"
        self.page.theme_mode = "light"  # Cambiado a light para combinar con el fondo claro
        self.page.padding = 0
        self.page.bgcolor = "#fbf5e9"

        self.vista_actual = "home"
        # view_switcher / content_container / layout_principal se arman
        # dentro de mostrar_panel() — recién ahí sabemos que hay sesión.
        self.view_switcher = None
        self.content_container = None
        self.layout_principal = None

        # SIEMPRE arranca en el login. La sesión NO se guarda en disco
        # (2026-09-05: se borró models/sesion.py y aquí se llamaba a
        # sesion.restaurar()), así que abrir la app siempre pide contraseña.
        # Es una decisión de NEGOCIO, no de seguridad — ver el bloque
        # "POR QUÉ EL LOGIN NO SE GUARDA" del roadmap: con la sesión viva,
        # cortarle la licencia a un local no surtía efecto hasta que
        # venciera su refresh_token; sin ella, el corte pega en el
        # siguiente arranque. Mismo criterio que mesas.js (persistSession:
        # false). OJO: la pantalla de login NO pasa por cambiar_vista() —
        # ocupa toda la ventana, sin Sidebar, así que se decide aquí, antes
        # de armar layout_principal (Fase 2.0).
        self.mostrar_login()

        self.page.window.maximized = True
        self.page.update()
        self.page.run_task(self._maximizar_ventana)

    async def _maximizar_ventana(self):
        await asyncio.sleep(0.2)
        self.page.window.maximized = True
        self.page.update()

    def mostrar_login(self):
        """Pantalla de arranque sin sesión: ocupa toda la ventana, sin
        Sidebar. No es una vista del panel — no se agrega a cambiar_vista()
        ni tiene botón en el sidebar."""
        self.page.controls.clear()
        self.page.add(SesionView(self))
        self.page.update()

    def mostrar_panel(self):
        """Arma el layout de siempre (Sidebar + contenido) y entra a Inicio.
        Solo se llama una vez hay una sesión activa en `client.auth` —
        desde __init__ (sesión restaurada) o desde SesionView tras un login
        exitoso."""
        self.view_switcher = ft.AnimatedSwitcher(
            content=ft.Container(expand=True),
            duration=360,
            reverse_duration=260,
            switch_in_curve=ft.AnimationCurve.EASE_OUT_CUBIC,
            switch_out_curve=ft.AnimationCurve.EASE_IN_CUBIC,
            transition=ft.AnimatedSwitcherTransition.SCALE,
            expand=True
        )

        self.content_container = ft.Container(
            expand=True,
            height=float("inf"),
            bgcolor="#fbf5e9",
            content=self.view_switcher
        )

        # Layout principal modularizado
        self.layout_principal = ft.Row(
            [
                Sidebar(self),
                self.content_container
            ],
            expand=True,
            height=float("inf"),
            spacing=0
        )

        self.page.controls.clear()
        self.page.add(self.layout_principal)

        self.cambiar_vista("home")
        self.page.update()

    def cerrar_sesion(self):
        """Cierra sesión y regresa al login. Se llama desde ajustes_view.py
        (Fase 8, el repaso final) — no hay botón para esto todavía en
        ningún lado.

        Ya no borra nada de disco (antes llamaba a sesion.borrar()): desde
        2026-09-05 la sesión solo vive en memoria, así que basta con el
        sign_out y volver al login."""
        try:
            client.auth.sign_out()
        except Exception as e:
            print(f"[sesion] sign_out falló, se ignora (la sesión local ya no sirve): {e}")
        self.mostrar_login()

    def cambiar_vista(self, vista: str, abrir_dialogo_nuevo: bool = False):
        """abrir_dialogo_nuevo: lo usa SOLO el atajo "Agregar un producto
        nuevo" de home_view.py (Fase 2.7) para llegar a Menú con el diálogo
        de alta ya abierto. Se pasa directo al constructor de MenuView en
        vez de guardarse como estado del router, para que no quede una
        bandera "pegada" que reabra el diálogo si después se entra a Menú
        por otro lado (sidebar, el otro atajo) — esos siguen llamando
        cambiar_vista("menu") sin el segundo argumento, que por default es
        False, exactamente el comportamiento de antes."""
        self.vista_actual = vista
        
        if vista == "home":
            vista_actual_widget = HomeView(self)
        elif vista == "menu":
            vista_actual_widget = MenuView(self, abrir_dialogo_nuevo=abrir_dialogo_nuevo)
        elif vista == "mesas":
            vista_actual_widget = MesasView(self)
        elif vista == "agente_financiero":
            vista_actual_widget = AgenteIAView(self)
        elif vista == "contenido":
            vista_actual_widget = ContenidoView(self)
        elif vista == "ajustes":
            vista_actual_widget = AjustesView(self)
        elif vista == "biblioteca":
            vista_actual_widget = BibliotecaView(self)
        else:
            vista_actual_widget = HomeView(self)
            
        vista_actual_widget.key = f"vista-{vista}"
        self.view_switcher.content = vista_actual_widget
        
        # Reconstruimos la barra para reflejar el botón activo.
        self.layout_principal.controls[0] = Sidebar(self)
        self.page.update()