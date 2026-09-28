import asyncio
import os
import traceback

import flet as ft

from models import perfil, saludo_ia
from models.supabase_client import client
from views import tema
from views.agenteIA_view import AgenteIAView
from views.ajustes_view import AjustesView
from views.barra_lateral import crear_barra_lateral
from views.biblioteca_view import BibliotecaView
from views.contenido_view import ContenidoView
from views.home_view import HomeView
from views.menu_view import MenuView
from views.mesas_view import MesasView
from views.piezas import aviso, sin_auto_update
from views.sesion_view import SesionView


class MainController:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Fragmentless - Panel"
        # El logo en la barra de título y en la de tareas (Flet solo acepta .ico y con ruta
        # absoluta). Si falta el archivo, la ventana se queda con el de Flet.
        icono = os.path.abspath("assets/icono.ico")
        if os.path.exists(icono):
            self.page.window.icon = icono
        # El tema elegido en Ajustes (config.json; el oscuro si no hay). Antes de crear ninguna
        # vista: cada una lee sus colores al construirse (views/tema.py).
        tema.cargar()
        self.page.theme_mode = tema.C.modo
        self.page.bgcolor = tema.C.fondo
        self.page.padding = 0
        # La letra del panel, registrada una sola vez: la barra lateral la usa en todas las
        # vistas. Las familias se llaman por lo que son: cambiar de fuente es cambiar dos líneas.
        fuentes = dict(getattr(self.page, "fonts", {}) or {})
        fuentes["LetraTitulo"] = "assets/PlusJakartaSans-Bold.ttf"
        fuentes["LetraTexto"] = "assets/PlusJakartaSans-Medium.ttf"
        # Coolvetica (condensada), solo para los números grandes de los contadores.
        fuentes["Coolvetica"] = "assets/Coolvetica Rg Cram.otf"
        self.page.fonts = fuentes
        # La letra por defecto de todo el panel: así ningún texto se queda en Roboto.
        self.page.theme = ft.Theme(font_family="LetraTexto")
        self.page.dark_theme = ft.Theme(font_family="LetraTexto")

        # Eventos de la ventana que llegan aunque nadie los escuche (el tema de Windows, el foco
        # de la ventana...). Sin manejador, Flet hace igual su auto-update, que compara la página
        # entera. Con un manejador vacío sin auto-update, nada (guía, B1 regla 2).
        nada = sin_auto_update(lambda e: None)
        self.page.on_platform_brightness_change = nada
        self.page.on_app_lifecycle_state_change = nada
        self.page.on_locale_change = nada
        self.page.on_media_change = nada

        self.vista_actual = None
        self.content_container = ft.Container(expand=True)
        self.page.add(self.content_container)

        # SIEMPRE arranca en el login. La sesión NO se guarda en disco (2026-09-05): es una
        # decisión de NEGOCIO — ver "POR QUÉ EL LOGIN NO SE GUARDA" del roadmap: con la sesión
        # viva, cortarle la licencia a un local no surtía efecto hasta que venciera su
        # refresh_token; sin ella, el corte pega en el siguiente arranque.
        self.mostrar_login()
        # El saludo del Agente IA se empieza a redactar YA, en la pantalla
        # de entrar: no lee la base (solo el apodo de config.json), así que
        # no necesita la sesión, y para cuando se termina de escribir la
        # contraseña ya está listo (models/saludo_ia.py).
        self.page.run_task(self.precargar_saludo)

        self.page.window.maximized = True
        self.page.update()
        self.page.run_task(self._maximizar_ventana)

    async def _maximizar_ventana(self):
        await asyncio.sleep(0.2)
        self.page.window.maximized = True
        self.page.update()

    def _poner_vista(self, vista):
        # Cambia la vista en DOS update(): primero entra la nueva, en un contenedor suyo junto al
        # de la vieja, que se esconde (lo que se ve cambia ya aquí); luego se quita la vieja. En
        # un solo update() Flet cruza cada control quitado con cada puesto, y con una vista
        # grande eso tardaba más de un segundo (guía, B1 regla 10).
        vieja = self.content_container
        self.content_container = ft.Container(expand=True, content=vista)
        vieja.visible = False
        self.page.controls.append(self.content_container)
        self.page.update()
        self.page.controls.remove(vieja)
        self.page.update()

    def mostrar_login(self, motivo=None):
        """La pantalla de entrar: ocupa toda la ventana, sin barra lateral. `motivo` es un aviso
        al llegar ("Cerraste sesión."), si lo hay."""
        self.vista_actual = None
        self._poner_vista(SesionView(self))
        if motivo:
            aviso(self.page, motivo, barra=0)

    def mostrar_panel(self):
        """Entra a Inicio. Solo se llama con una sesión activa en `client.auth` (desde
        SesionView tras un login exitoso y con la licencia activa)."""
        self.cambiar_vista("home")
        # Por si el de la pantalla de entrar falló o ya no corresponde (otro
        # apodo, otro momento del día); si sigue sirviendo, no pide nada.
        self.page.run_task(self.precargar_saludo)

    async def precargar_saludo(self):
        """Deja un saludo del Agente IA en reserva, en segundo plano. Lo
        llaman mostrar_panel() y la vista del agente al gastar el suyo."""
        try:
            await asyncio.to_thread(saludo_ia.preparar, perfil.como_llamarte())
        except Exception:
            traceback.print_exc()

    async def cerrar_sesion(self):
        """Cierra la sesión y vuelve a la pantalla de entrar. El sign_out va en un hilo aparte
        (es red) y SOLO en esta PC (scope "local"): el valor por defecto de supabase-py es
        GLOBAL, y como los meseros entran a mesas.html con el mismo usuario, les tiraba la
        sesión también. Si el servidor no contesta da igual: la sesión solo vive en memoria."""
        try:
            await asyncio.to_thread(client.auth.sign_out, {"scope": "local"})
        except Exception:
            traceback.print_exc()
        self.mostrar_login("Cerraste sesión.")

    def cambiar_tema(self, nombre):
        # Lo llama Ajustes al elegir otro tema: se guarda y se rehace Ajustes (con su barra) ya
        # con los colores nuevos; las demás vistas se construyen con ellos al abrirlas. La capa
        # de la ventana Perfil vive en page.overlay (se crea una vez): se quita para que la
        # próxima vez nazca con el velo del tema nuevo.
        tema.guardar(nombre)
        self.page.theme_mode = tema.C.modo
        self.page.bgcolor = tema.C.fondo
        ventana = getattr(self, "ventana_perfil", None)
        if ventana is not None:
            self.page.overlay.remove(ventana["capa"])
            self.ventana_perfil = None
        self.cambiar_vista("ajustes")

    def cambiar_vista(self, vista: str, abrir_dialogo_nuevo: bool = False):
        """abrir_dialogo_nuevo: lo usa SOLO el atajo "Agregar un producto nuevo" de Inicio para
        llegar a Mi menú con el diálogo de alta ya abierto. Se pasa directo al constructor de
        MenuView (no como estado del router) para que no quede una bandera "pegada"."""
        self.vista_actual = vista

        if vista == "home":
            widget = HomeView(self)
        elif vista == "menu":
            widget = MenuView(self, abrir_dialogo_nuevo=abrir_dialogo_nuevo)
        elif vista == "mesas":
            widget = MesasView(self)
        elif vista == "agente_financiero":
            widget = AgenteIAView(self)
        elif vista == "contenido":
            widget = ContenidoView(self)
        elif vista == "ajustes":
            widget = AjustesView(self)
        elif vista == "biblioteca":
            widget = BibliotecaView(self)
        else:
            self.vista_actual = "home"
            widget = HomeView(self)

        # La barra y la vista, lado a lado. La barra se rehace con cada vista (marca la activa).
        self._poner_vista(ft.Row(
            [crear_barra_lateral(self, self.vista_actual), widget],
            expand=True, spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        ))
