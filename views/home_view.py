import flet as ft
import datetime

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
                        self._crear_tarjeta_stat("PRODUCTOS EN VENTA", "10 Platillos", "1 categoría", ft.Icons.REORDER_ROUNDED),
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
                                            self._crear_boton_atajo("Agregar un producto nuevo", "Crea productos con descripciones", ft.Icons.ADD_CIRCLE_OUTLINE, "#c86a28", "menu"),
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
                            ft.Text("No hay cambios recientes registrados hoy.", size=13, color="#998e80", italic=True)
                        ],
                        spacing=4
                    )
                )
            ],
            spacing=0,
            scroll=ft.ScrollMode.AUTO
        )

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

    def _crear_boton_atajo(self, titulo: str, subtitulo: str, icono: str, color_icono: str, ruta: str):
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
            on_click=lambda _: self.router.cambiar_vista(ruta),
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