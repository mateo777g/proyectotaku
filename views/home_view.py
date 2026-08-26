import asyncio
import datetime

import flet as ft
import httpx

from models.platillo_dao import PlatilloDAO


def _texto_platillos(cantidad: int) -> str:
    """'1 Platillo' vs 'N Platillos' — mismo cuidado de singular que
    _texto_contador() en menu_view.py."""
    if cantidad == 1:
        return "1 Platillo"
    return f"{cantidad} Platillos"


def _texto_categorias(cantidad: int) -> str:
    """'1 categoría' vs 'N categorías'."""
    if cantidad == 1:
        return "1 categoría"
    return f"{cantidad} categorías"


def _analizar_fecha(valor):
    """Parsea el timestamp ISO que regresa Supabase (con o sin sufijo 'Z')
    a un datetime con zona horaria. None si viene vacío o mal formado —
    _tiempo_relativo ya sabe qué hacer con eso (texto vacío)."""
    if not valor:
        return None
    try:
        return datetime.datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _tiempo_relativo(valor: str) -> str:
    """'hace 2 horas' / 'ayer' / 'hace 3 días' / 'el 12 de agosto' — para la
    tarjeta "Lo último de tu menú" (Fase 2.7). Convierte el timestamp UTC
    que regresa Supabase a la hora local de la máquina (mismo criterio que
    datetime.now(), ya usado abajo para el saludo) antes de comparar días
    de calendario, para que "ayer" caiga donde de verdad cayó para el
    dueño, no en UTC."""
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

    dias_diferencia = (ahora.date() - fecha_local.date()).days
    if dias_diferencia <= 0:
        horas = int(segundos // 3600)
        return "hace 1 hora" if horas == 1 else f"hace {horas} horas"
    if dias_diferencia == 1:
        return "ayer"
    if dias_diferencia < 7:
        return f"hace {dias_diferencia} días"

    meses_min = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ]
    return f"el {fecha_local.day} de {meses_min[fecha_local.month - 1]}"


class HomeView(ft.Container):
    def __init__(self, router):
        super().__init__()
        self.router = router
        self.page_ref = router.page
        self.expand = True
        self.height = float("inf")
        self.bgcolor = "#fbf5e9"
        self.padding = ft.padding.only(left=36, right=36, top=42, bottom=36)

        # Lógica para la fecha dinámica
        dias = ["LUNES", "MARTES", "MIÉRCOLES", "JUEVES", "VIERNES", "SÁBADO", "DOMINGO"]
        meses = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
        hoy = datetime.datetime.now()
        fecha_texto = f"{dias[hoy.weekday()]}, {hoy.day} DE {meses[hoy.month - 1]}"
        dia_actual = dias[hoy.weekday()].capitalize()

        # Fase 2.7: los "cuerpos" de las 2 tarjetas que sí dependen del menú
        # se crean ANTES de armar self.content (van referenciados adentro) y
        # arrancan en su estado de "cargando" — _cargar_estadisticas() y
        # _cargar_recientes() los reemplazan de verdad al final de __init__.
        self.cuerpo_stat_productos = ft.Column(
            spacing=6,
            controls=self._estado_cargando_stat(),
        )
        self.cuerpo_recientes = ft.Column(
            spacing=8,
            controls=self._estado_cargando_recientes(),
        )

        self.content = ft.Column(
            expand=True,
            height=float("inf"),
            controls=[
                # --- CABECERA ---
                ft.Row(
                    controls=[
                        ft.Column(
                            controls=[
                                ft.Text(fecha_texto, color="#b58a6d", size=18, weight="bold"),
                                ft.Row(
                                    controls=[
                                        ft.Text("Buenos días, ", size=48, font_family="Georgia", italic=True, color="#18120d"),
                                        ft.Text("Ary", size=48, font_family="Georgia", italic=True, color="#bf571d"),
                                    ],
                                    spacing=0
                                ),
                                ft.Row(
                                    controls=[
                                        ft.Text("Tu menú se vio ", size=20, color="#5e5449"),
                                        ft.Text("347 veces", size=20, weight="bold", color="#1c1610"),
                                        ft.Text(" ayer. Aquí está el resumen.", size=20, color="#5e5449"),
                                    ],
                                    spacing=0
                                )
                            ],
                            spacing=2,
                            expand=True
                        ),
                        ft.Container(
                            content=ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.AUTO_AWESOME, color="#e8aa3a", size=22),
                                    ft.Text("Crear contenido", color="#ffffff", weight="bold", size=16)
                                ],
                                spacing=8
                            ),
                            margin=ft.margin.only(top=78),
                            bgcolor="#0d0905",
                            padding=ft.padding.symmetric(horizontal=26, vertical=16),
                            border_radius=30,
                            shadow=ft.BoxShadow(
                                blur_radius=14,
                                spread_radius=1,
                                color=ft.Colors.with_opacity(0.32, ft.Colors.BLACK),
                                offset=ft.Offset(0, 5)
                            ),
                            ink=True,
                            on_click=lambda _: self.router.cambiar_vista("contenido")
                        )
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.START
                ),

                ft.Container(height=38),

                # --- FILA DE 4 TARJETAS DE ESTADÍSTICAS ---
                ft.Row(
                    controls=[
                        self._crear_tarjeta_stat("VISITAS AL MENÚ", "347", "+12% vs ayer", ft.Icons.SHOW_CHART),
                        self._crear_tarjeta_stat("PRODUCTO MÁS VISTO", "Tacos al Pastor", "48 órdenes", ft.Icons.LOCAL_FIRE_DEPARTMENT_OUTLINED),
                        self._crear_tarjeta_stat("CONTENIDO GENERADO", "12 Posts", "Este mes", ft.Icons.AUTO_AWESOME_OUTLINED),
                        self._crear_tarjeta_productos_en_venta(),
                    ],
                    spacing=24
                ),

                ft.Container(height=30),

                # --- FILA CENTRAL: ¿Qué hacemos hoy? + Sugerencia IA ---
                ft.Row(
                    controls=[
                        ft.Container(
                            expand=3,
                            height=300,
                            bgcolor="#f8f1de",
                            border_radius=20,
                            padding=22,
                            shadow=ft.BoxShadow(
                                blur_radius=12,
                                spread_radius=0,
                                color=ft.Colors.with_opacity(0.28, "#ffa200"),
                                offset=ft.Offset(0, 4)
                            ),
                            content=ft.Column(
                                controls=[
                                    ft.Text("¿Qué hacemos hoy?", size=23, font_family="Georgia", weight="bold", italic=True, color="#1c1610"),
                                    ft.Text("Atajos a las tareas que más usas.", size=13, color="#7c7267"),
                                    ft.Container(height=12),
                                    ft.Row(
                                        controls=[
                                            self._crear_boton_atajo("Crear post para Instagram", "Imagenes promocionales automáticas", ft.Icons.AUTO_AWESOME, "#e8aa3a", "contenido"),
                                            self._crear_boton_atajo("Marcar un platillo como agotado", "Se oculta automáticamente de tu menú", ft.Icons.BLOCK, "#d9534f", "menu"),
                                        ],
                                        spacing=10
                                    ),
                                    ft.Row(
                                        controls=[
                                            self._crear_boton_atajo("Agregar un producto nuevo", "Crea productos con descripciones", ft.Icons.ADD_CIRCLE_OUTLINE, "#c86a28", "menu", abrir_dialogo_nuevo=True),
                                            self._crear_boton_atajo("Administrar finanzas con IA", "Analiza y optimiza tu negocio", ft.Icons.PRICE_CHANGE_OUTLINED, "#5b8c5a", "agente_financiero"),
                                        ],
                                        spacing=10
                                    )
                                ],
                                spacing=4
                            )
                        ),

                        ft.Container(
                            expand=2,
                            height=300,
                            bgcolor="#0d0905",
                            border_radius=20,
                            padding=22,
                            shadow=ft.BoxShadow(
                                blur_radius=16,
                                spread_radius=0,
                                color=ft.Colors.with_opacity(0.36, ft.Colors.BLACK),
                                offset=ft.Offset(0, 6)
                            ),
                            content=ft.Column(
                                controls=[
                                    ft.Text("SUGERENCIA DE HOY", size=12, weight="bold", color="#8b7764"),
                                    ft.Text(f"Es {dia_actual} en Mendoza. ¿Qué tal un post del Argile para la noche?", size=23, font_family="Georgia", weight="bold", italic=True, color="#ffffff"),
                                    ft.Text("Llevas 3 semanas sin postear Argile y los viernes históricamente generan +40% de interés.", size=14, color="#b2a69a"),
                                    ft.Container(height=14),
                                    ft.Container(
                                        content=ft.Row(
                                            controls=[
                                                ft.Icon(ft.Icons.AUTO_AWESOME, color="#0d0905", size=19),
                                                ft.Text("Generar post", color="#0d0905", weight="bold", size=15)
                                            ],
                                            alignment=ft.MainAxisAlignment.CENTER,
                                            spacing=8
                                        ),
                                        width=210,
                                        bgcolor="#e8aa3a",
                                        padding=ft.padding.symmetric(vertical=15, horizontal=16),
                                        border_radius=24,
                                        ink=True,
                                        on_click=lambda _: self.router.cambiar_vista("contenido")
                                    )
                                ],
                                spacing=8,
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                            )
                        )
                    ],
                    spacing=16
                ),

                ft.Container(height=42),

                # --- FILA INFERIOR: Lo último de tu menú ---
                ft.Container(
                    width=float("inf"),
                    height=185,
                    bgcolor="#f8f1de",
                    border_radius=20,
                    padding=22,
                    shadow=ft.BoxShadow(
                        blur_radius=12,
                        spread_radius=0,
                        color=ft.Colors.with_opacity(0.28, "#ffa200"),
                        offset=ft.Offset(0, 4)
                    ),
                    content=ft.Column(
                        controls=[
                            ft.Text("Lo último de tu menú", size=21, font_family="Georgia", weight="bold", italic=True, color="#1c1610"),
                            ft.Text("Cambios y publicaciones recientes.", size=12, color="#7c7267"),
                            ft.Container(height=10),
                            self.cuerpo_recientes,
                        ],
                        spacing=4
                    )
                )
            ],
            spacing=0,
            scroll=ft.ScrollMode.AUTO
        )

        # Fase 2.7: dispara la carga real de las 2 tarjetas que sí dependen
        # del menú apenas se monta la vista — mismo patrón que menu_view.py
        # (page.run_task + asyncio.to_thread), cada una en su propio
        # try/except para que si una falla no tumbe a la otra ni al resto
        # de Inicio.
        self.router.page.run_task(self._cargar_estadisticas)
        self.router.page.run_task(self._cargar_recientes)

    def _crear_tarjeta_stat(self, titulo: str, valor: str, subtitulo: str, icono: str):
        return ft.Container(
            expand=True,
            height=170,
            bgcolor="#f8f1de",
            border_radius=18,
            padding=22,
            shadow=ft.BoxShadow(
                blur_radius=10,
                spread_radius=0,
                color=ft.Colors.with_opacity(0.28, "#ffa200"),
                offset=ft.Offset(0, 3)
            ),
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text(titulo, size=11, weight="bold", color="#806f61", expand=True),
                            ft.Icon(icono, color="#c86a28", size=16)
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                    ),
                    ft.Text(valor, size=25, weight="bold", color="#1c1610"),
                    ft.Text(subtitulo, size=13, color="#7c7267")
                ],
                spacing=6
            )
        )

    def _crear_tarjeta_productos_en_venta(self):
        """Versión dinámica de _crear_tarjeta_stat() para "PRODUCTOS EN
        VENTA" (Fase 2.7) — mismo contenedor/sombra/tamaño que las otras 3
        tarjetas de la fila, pero el valor+subtítulo viven en
        self.cuerpo_stat_productos para poder reemplazarlos cuando
        _cargar_estadisticas() responda, sin reconstruir toda la tarjeta."""
        return ft.Container(
            expand=True,
            height=170,
            bgcolor="#f8f1de",
            border_radius=18,
            padding=22,
            shadow=ft.BoxShadow(
                blur_radius=10,
                spread_radius=0,
                color=ft.Colors.with_opacity(0.28, "#ffa200"),
                offset=ft.Offset(0, 3)
            ),
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text("PRODUCTOS EN VENTA", size=11, weight="bold", color="#806f61", expand=True),
                            ft.Icon(ft.Icons.REORDER_ROUNDED, color="#c86a28", size=16)
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                    ),
                    self.cuerpo_stat_productos,
                ],
                spacing=6
            )
        )

    def _crear_boton_atajo(self, titulo: str, subtitulo: str, icono: str, color_icono: str, ruta: str, abrir_dialogo_nuevo: bool = False):
        return ft.Container(
            expand=True,
            bgcolor="#f8f1de",
            border=ft.border.all(1, "#f4ca83"),
            border_radius=30,
            padding=14,
            shadow=ft.BoxShadow(
                blur_radius=8,
                spread_radius=0,
                color=ft.Colors.with_opacity(0.18, "#f4ca83"),
                offset=ft.Offset(0, 2)
            ),
            ink=True,
            on_click=lambda _: self.router.cambiar_vista(ruta, abrir_dialogo_nuevo),
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(icono, color=color_icono, size=20),
                        bgcolor="#f8f1de",
                        padding=10,
                        border_radius=10
                    ),
                    ft.Column(
                        controls=[
                            ft.Text(titulo, size=13, weight="bold", color="#1c1610"),
                            ft.Text(subtitulo, size=10, color="#8a7e72")
                        ],
                        spacing=2,
                        expand=True
                    )
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            )
        )

    # ------------------------------------------------------------------
    # Fase 2.7 — "PRODUCTOS EN VENTA": conteo real contra public.platillos
    # ------------------------------------------------------------------
    def _estado_cargando_stat(self):
        return [
            ft.Row(
                controls=[
                    ft.ProgressRing(width=16, height=16, stroke_width=2, color="#f4ca83"),
                    ft.Text("Cargando...", size=13, color="#7c7267"),
                ],
                spacing=8,
            )
        ]

    def _estado_error_stat(self):
        return [
            ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE, size=14, color="#d9534f"),
                    ft.Text("No se pudo cargar.", size=12, color="#a33c39"),
                ],
                spacing=6,
            )
        ]

    async def _cargar_estadisticas(self):
        try:
            # Llamada bloqueante (supabase-py es síncrono) — a un hilo
            # aparte para no congelar la ventana, mismo patrón que
            # _cargar_platillos en menu_view.py.
            stats = await asyncio.to_thread(PlatilloDAO.obtener_estadisticas)
        except httpx.RequestError as e:
            print(f"[home] error de red al traer estadísticas del menú: {e}")
            self.cuerpo_stat_productos.controls = self._estado_error_stat()
            self.cuerpo_stat_productos.update()
            return
        except Exception as e:
            print(f"[home] error al traer estadísticas del menú: {e}")
            self.cuerpo_stat_productos.controls = self._estado_error_stat()
            self.cuerpo_stat_productos.update()
            return

        self.cuerpo_stat_productos.controls = [
            ft.Text(_texto_platillos(stats["total"]), size=25, weight="bold", color="#1c1610"),
            ft.Text(_texto_categorias(stats["categorias_en_uso"]), size=13, color="#7c7267"),
        ]
        self.cuerpo_stat_productos.update()

    # ------------------------------------------------------------------
    # Fase 2.7 — "Lo último de tu menú": altas y ediciones reales
    # ------------------------------------------------------------------
    def _estado_cargando_recientes(self):
        return [
            ft.Row(
                controls=[
                    ft.ProgressRing(width=16, height=16, stroke_width=2, color="#f4ca83"),
                    ft.Text("Cargando...", size=13, color="#7c7267"),
                ],
                spacing=8,
            )
        ]

    def _estado_error_recientes(self):
        return [
            ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE, size=14, color="#d9534f"),
                    ft.Text("No se pudieron cargar los últimos movimientos.", size=12, color="#a33c39"),
                ],
                spacing=6,
            )
        ]

    def _estado_vacio_recientes(self):
        return [
            ft.Text(
                "Todavía no hay movimientos registrados en tu menú.",
                size=13,
                color="#998e80",
                italic=True,
            )
        ]

    def _fila_reciente(self, platillo: dict):
        """Una línea de la lista: puntito de color + nombre + etiqueta con
        tiempo relativo. Mismo lenguaje que _badge_visibilidad() de
        menu_view.py (puntito 7x7 + texto), aplicado a una fila en vez de
        un badge — verde (#7d8545, el mismo "ok/visible" que ya usa ese
        badge) para altas, naranja (#c86a28, el mismo color de ícono que ya
        usan las tarjetas de esta fila) para ediciones."""
        es_nuevo = platillo.get("created_at") == platillo.get("updated_at")
        etiqueta = "Nuevo" if es_nuevo else "Editado"
        color_punto = "#7d8545" if es_nuevo else "#c86a28"
        tiempo = _tiempo_relativo(platillo.get("updated_at"))

        return ft.Row(
            controls=[
                ft.Container(width=7, height=7, bgcolor=color_punto, border_radius=4),
                ft.Text(
                    platillo.get("nombre") or "",
                    size=13,
                    weight="bold",
                    color="#1c1610",
                    expand=True,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                ft.Text(f"{etiqueta} · {tiempo}", size=12, color="#8a7e72"),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    async def _cargar_recientes(self):
        try:
            # Tope de 3 filas: el Container de esta tarjeta tiene
            # height=185 fijo a propósito (ver CLAUDE.md/roadmap) y 3 es lo
            # que cabe cómodo junto al título/subtítulo sin apretarse ni
            # desbordar — verificado con screenshot real, no a ojo.
            recientes = await asyncio.to_thread(PlatilloDAO.obtener_recientes, 3)
        except httpx.RequestError as e:
            print(f"[home] error de red al traer lo último del menú: {e}")
            self.cuerpo_recientes.controls = self._estado_error_recientes()
            self.cuerpo_recientes.update()
            return
        except Exception as e:
            print(f"[home] error al traer lo último del menú: {e}")
            self.cuerpo_recientes.controls = self._estado_error_recientes()
            self.cuerpo_recientes.update()
            return

        if not recientes:
            self.cuerpo_recientes.controls = self._estado_vacio_recientes()
        else:
            self.cuerpo_recientes.controls = [self._fila_reciente(p) for p in recientes]
        self.cuerpo_recientes.update()
