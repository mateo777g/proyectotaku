"""
views/home_view.py
Inicio. Misma estructura y mismos textos de siempre (cabecera con "Crear contenido", 4
tarjetas de datos, "¿Qué hacemos hoy?" + "Sugerencia de hoy", "Lo último de tu menú"),
pintada con el diseño oscuro de la guía (views/tema.py + views/piezas.py).

Real: la fecha, el saludo por la hora, "PRODUCTOS EN VENTA" y "Lo último de tu menú".
Todavía de ejemplo (Fase 8): "VISITAS AL MENÚ", "PRODUCTO MÁS VISTO", "CONTENIDO GENERADO",
la frase de visitas y la SUGERENCIA DE HOY.
"""
import asyncio
import datetime
import traceback

import flet as ft

from models import perfil
from models.platillo_dao import PlatilloDAO
from models.tiempo import saludo_por_hora
from views.piezas import (CURVA, ZOOM, anillo_brillo, boton_atajo, fecha_vista, fondo_pagina,
                          relevo, sin_auto_update, tarjeta_iphone, titulo_vista)
from views.tema import C

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MESES_MIN = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
             "septiembre", "octubre", "noviembre", "diciembre"]


def _texto_platillos(cantidad):
    return "1 Platillo" if cantidad == 1 else f"{cantidad} Platillos"


def _texto_categorias(cantidad):
    return "1 categoría" if cantidad == 1 else f"{cantidad} categorías"


def _analizar_fecha(valor):
    if not valor:
        return None
    try:
        return datetime.datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _tiempo_relativo(valor):
    """'hace 2 horas' / 'ayer' / 'hace 3 días' / 'el 12 de agosto', en hora local."""
    fecha = _analizar_fecha(valor)
    if fecha is None:
        return ""
    fecha_local = fecha.astimezone()
    ahora = datetime.datetime.now().astimezone()
    segundos = (ahora - fecha_local).total_seconds()
    if segundos < 60:
        return "hace un momento"
    if segundos < 3600:
        minutos = int(segundos // 60)
        return "hace 1 minuto" if minutos == 1 else f"hace {minutos} minutos"
    dias = (ahora.date() - fecha_local.date()).days
    if dias <= 0:
        horas = int(segundos // 3600)
        return "hace 1 hora" if horas == 1 else f"hace {horas} horas"
    if dias == 1:
        return "ayer"
    if dias < 7:
        return f"hace {dias} días"
    return f"el {fecha_local.day} de {MESES_MIN[fecha_local.month - 1]}"


def _texto(valor, tam=13, suave=False, titulo=False, **kw):
    return ft.Text(valor, size=tam, color=C.texto_suave if suave else C.texto,
                   font_family="LetraTitulo" if titulo else "LetraTexto", **kw)


def atajo_doble(icono, titulo, subtitulo, al_pulsar):
    # Los atajos de "¿Qué hacemos hoy?" de siempre (título + subtítulo), con la piel de un botón
    # de la guía: cara translúcida, brillo en dos esquinas, zoom 1.05 y relevo al pasar el cursor.
    alto = 60
    radio = alto / 2

    def fila():
        return ft.Row([
            ft.Icon(icono, color=C.texto, size=20),
            ft.Column([
                _texto(titulo, 13, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                _texto(subtitulo, 10, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ], spacing=2, tight=True, expand=True),
        ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    rodillo, encender_relevo = relevo(fila)
    cara = ft.Container(
        left=0, top=0, right=0, bottom=0, bgcolor=C.cara, border_radius=radio,
        padding=ft.Padding(left=22, top=0, right=18, bottom=0),
        alignment=ft.Alignment.CENTER_LEFT, content=rodillo,
        animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT),
    )
    boton = ft.Container(
        height=alto, expand=True, scale=1, animate_scale=CURVA,
        content=ft.Stack([
            anillo_brillo(ft.Alignment(-1, -1), radio, alto),
            anillo_brillo(ft.Alignment(1, 1), radio, alto),
            cara,
        ], clip_behavior=ft.ClipBehavior.NONE),
    )

    def encender(dentro):
        boton.scale = ZOOM if dentro else 1
        cara.bgcolor = C.cara_encendida if dentro else C.cara
        encender_relevo(dentro)
        boton.update()

    def hundir(_):
        boton.scale = 0.97
        cara.bgcolor = C.cara_pulsada
        boton.update()

    cara.on_hover = sin_auto_update(lambda e: encender(e.data in (True, "true")))
    cara.on_tap_down = sin_auto_update(hundir)
    cara.on_click = sin_auto_update(al_pulsar)
    return boton


class HomeView(ft.Container):
    def __init__(self, router):
        super().__init__()
        self.router = router
        self.page_ref = router.page
        self.expand = True
        self.bgcolor = C.fondo
        self.gradient = fondo_pagina()
        self.padding = 40

        hoy = datetime.datetime.now()
        dia_actual = DIAS[hoy.weekday()]
        saludo = saludo_por_hora(hoy.hour)

        # El nombre del saludo: el del Perfil (pie de la barra). Al guardarlo se repinta aquí.
        self.saludo_nombre = titulo_vista(perfil.como_llamarte())
        self.router.pintores_perfil = dict(getattr(router, "pintores_perfil", None) or {},
                                           saludo=self._pintar_saludo)

        # Lo que llega de Supabase: arranca en "Cargando…".
        self.cuerpo_stat_productos = ft.Column(
            [_texto("Cargando…", 13, suave=True)], spacing=6)
        self.cuerpo_recientes = ft.Column(
            [_texto("Cargando…", 13, suave=True)], spacing=0)

        self.content = ft.Column([
            # --- CABECERA ---
            ft.Row([
                ft.Column([
                    fecha_vista(),
                    ft.Row([titulo_vista(f"{saludo},"), self.saludo_nombre], spacing=10),
                    ft.Row([
                        _texto("Tu menú se vio ", 16, suave=True),
                        _texto("0 veces", 16, titulo=True),
                        _texto(" ayer. Aquí está el resumen.", 16, suave=True),
                    ], spacing=0),
                ], spacing=2, expand=True),
                boton_atajo(ft.Icons.AUTO_AWESOME_OUTLINED, "Crear contenido",
                            lambda _: self.router.cambiar_vista("contenido"), ancho=200),
            ], vertical_alignment=ft.CrossAxisAlignment.END),

            ft.Container(height=25),

            # --- FILA DE 4 TARJETAS DE ESTADÍSTICAS ---
            ft.Row([
                self._tarjeta_stat("VISITAS AL MENÚ", ft.Icons.SHOW_CHART, ft.Column([
                    _texto("0", 25, titulo=True), _texto("+0% vs ayer", 13, suave=True)], spacing=6)),
                self._tarjeta_stat("PRODUCTO MÁS VISTO", ft.Icons.LOCAL_FIRE_DEPARTMENT_OUTLINED, ft.Column([
                    _texto("Ninguno", 25, titulo=True), _texto("0 órdenes", 13, suave=True)], spacing=6)),
                self._tarjeta_stat("CONTENIDO GENERADO", ft.Icons.AUTO_AWESOME_OUTLINED, ft.Column([
                    _texto("0 Posts", 25, titulo=True), _texto("Este mes", 13, suave=True)], spacing=6)),
                self._tarjeta_stat("PRODUCTOS EN VENTA", ft.Icons.LIST_ALT_OUTLINED,
                                   self.cuerpo_stat_productos),
            ], spacing=10, height=150, vertical_alignment=ft.CrossAxisAlignment.STRETCH),

            ft.Container(height=10),

            # --- FILA CENTRAL: ¿Qué hacemos hoy? + Sugerencia de hoy ---
            ft.Row([
                tarjeta_iphone(ft.Column([
                    _texto("¿QUÉ HACEMOS HOY?", 16, titulo=True),
                    _texto("Atajos a las tareas que más usas.", 12, suave=True),
                    ft.Container(height=15),
                    ft.Row([
                        atajo_doble(ft.Icons.AUTO_AWESOME_OUTLINED, "Crear post para Instagram",
                                    "Imagenes promocionales automáticas", self._ir("contenido")),
                        atajo_doble(ft.Icons.BLOCK, "Marcar un platillo como agotado",
                                    "Se oculta automáticamente de tu menú", self._ir("menu")),
                    ], spacing=12),
                    ft.Container(height=10),
                    ft.Row([
                        atajo_doble(ft.Icons.ADD_CIRCLE_OUTLINE, "Agregar un producto nuevo",
                                    "Crea productos con descripciones", self._ir("menu", True)),
                        atajo_doble(ft.Icons.PRICE_CHANGE_OUTLINED, "Administrar finanzas con IA",
                                    "Analiza y optimiza tu negocio", self._ir("agente_financiero")),
                    ], spacing=12),
                ], spacing=0), expand=3),

                tarjeta_iphone(ft.Column([
                    _texto("SUGERENCIA DE HOY", 12, suave=True),
                    ft.Container(height=8),
                    _texto(f"Es {dia_actual} en Rio Blanco. ¿Qué tal un post de Taco Arabe para la noche?",
                           22, titulo=True),
                    ft.Container(height=8),
                    _texto(f"Las noches de {dia_actual.lower()} son buen momento para publicar. "
                           "Genera el post en un clic.", 13, suave=True),
                    ft.Container(expand=True),
                    ft.Row([boton_atajo(ft.Icons.AUTO_AWESOME_OUTLINED, "Generar post",
                                        lambda _: self.router.cambiar_vista("contenido"), ancho=200)]),
                ], spacing=0), expand=2),
            ], spacing=10, height=270, vertical_alignment=ft.CrossAxisAlignment.STRETCH),

            ft.Container(height=10),

            # --- FILA INFERIOR: Lo último de tu menú ---
            ft.Row([
                tarjeta_iphone(ft.Column([
                    _texto("LO ÚLTIMO DE TU MENÚ", 16, titulo=True),
                    _texto("Cambios y publicaciones recientes.", 12, suave=True),
                    ft.Container(height=12),
                    self.cuerpo_recientes,
                ], spacing=0)),
            ]),
        ], spacing=0, scroll=ft.ScrollMode.AUTO)

    def did_mount(self):
        self.page_ref.run_task(self._cargar_estadisticas)
        self.page_ref.run_task(self._cargar_recientes)

    def _ir(self, ruta, abrir_dialogo_nuevo=False):
        return lambda _: self.router.cambiar_vista(ruta, abrir_dialogo_nuevo)

    def _pintar_saludo(self):
        try:
            self.saludo_nombre.value = perfil.como_llamarte()
            self.saludo_nombre.update()
        except RuntimeError:
            pass    # Inicio ya no está en pantalla

    def _tarjeta_stat(self, titulo, icono, cuerpo):
        return tarjeta_iphone(ft.Column([
            ft.Row([
                _texto(titulo, 12, suave=True, expand=True),
                ft.Icon(icono, color=C.texto_suave, size=16),
            ]),
            ft.Container(height=4),
            cuerpo,
        ], spacing=0), padding=22)

    def _actualizar(self, *controles):
        try:
            for c in controles:
                c.update()
        except RuntimeError:
            pass    # se salió de Inicio antes de que llegaran los datos

    async def _cargar_estadisticas(self):
        try:
            stats = await asyncio.to_thread(PlatilloDAO.obtener_estadisticas)
        except Exception:
            traceback.print_exc()
            self.cuerpo_stat_productos.controls = [_texto("No se pudo cargar.", 13, suave=True)]
        else:
            self.cuerpo_stat_productos.controls = [
                _texto(_texto_platillos(stats["total"]), 25, titulo=True),
                _texto(_texto_categorias(stats["categorias_en_uso"]), 13, suave=True),
            ]
        self._actualizar(self.cuerpo_stat_productos)

    def _fila_reciente(self, platillo):
        es_nuevo = platillo.get("created_at") == platillo.get("updated_at")
        etiqueta = "Nuevo" if es_nuevo else "Editado"
        return ft.Container(height=30, content=ft.Row([
            ft.Container(width=6, height=6, border_radius=3,
                         bgcolor=C.texto if es_nuevo else None,
                         border=None if es_nuevo else ft.Border.all(1, C.texto_suave)),
            _texto(platillo.get("nombre") or "", 13, titulo=True, expand=True,
                   max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            _texto(f"{etiqueta} · {_tiempo_relativo(platillo.get('updated_at'))}", 12, suave=True),
        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER))

    async def _cargar_recientes(self):
        try:
            recientes = await asyncio.to_thread(PlatilloDAO.obtener_recientes, 3)
        except Exception:
            traceback.print_exc()
            self.cuerpo_recientes.controls = [
                _texto("No se pudieron cargar los últimos movimientos.", 13, suave=True)]
        else:
            if not recientes:
                self.cuerpo_recientes.controls = [
                    _texto("Todavía no hay movimientos registrados en tu menú.", 13, suave=True)]
            else:
                self.cuerpo_recientes.controls = [self._fila_reciente(p) for p in recientes]
        self._actualizar(self.cuerpo_recientes)
