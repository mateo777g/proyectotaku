import flet as ft


class ContenidoView(ft.Container):
    def __init__(self, router):
        super().__init__()
        self.router = router
        self.expand = True
        self.height = float("inf")
        self.bgcolor = "#fbf5e9"
        self.padding = ft.padding.only(left=36, right=36, top=42, bottom=36)

        self.content = ft.Column(
            expand=True,
            height=float("inf"),
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.Text("CREAR CONTENIDO", size=13, weight="bold", color="#b58a6d"),
                ft.Text(
                    "Hagamos algo bonito para Instagram",
                    size=42,
                    font_family="Georgia",
                    italic=True,
                    color="#18120d",
                ),
                ft.Text(
                    "Elige un estilo para comenzar tu próxima publicación.",
                    size=15,
                    color="#7c7267",
                ),
                ft.Container(height=24),
                ft.Row(
                    controls=[
                        self._paso("1", "Elegir tipo de anuncio", activo=True, completado=True),
                        self._paso("2", "Elegir platillo"),
                        self._paso("3", "Instrucciones"),
                    ],
                    spacing=14,
                    alignment=ft.MainAxisAlignment.START,
                ),
                ft.Container(height=24),
                ft.Row(
                    controls=[
                        self._pestana("Continuo", activa=True),
                        self._pestana("Comida rápida", activa=False),
                    ],
                    spacing=34,
                ),
                ft.Container(height=18),
                ft.Container(
                    bgcolor="#f8f1de",
                    border_radius=24,
                    padding=ft.padding.only(left=28, right=28, top=26, bottom=24),
                    shadow=ft.BoxShadow(
                        blur_radius=22,
                        spread_radius=1,
                        color=ft.Colors.with_opacity(0.22, "#030303"),
                        offset=ft.Offset(0, 7),
                    ),
                    content=ft.Column(
                        spacing=0,
                        controls=[
                            ft.Text(
                                "Estilo Continuo",
                                size=22,
                                font_family="Georgia",
                                weight="bold",
                                italic=True,
                                color="#1c1610",
                            ),
                            ft.Text(
                                "Una composición consistente para que tu marca se reconozca en cada publicación.",
                                size=13,
                                color="#7c7267",
                            ),
                            ft.Container(height=22),
                            ft.Row(
                                controls=[
                                    self._muestra("assets/img1.png", "Producto protagonista"),
                                    self._muestra("assets/img2.png", "Detalle del platillo"),
                                    self._muestra("assets/img3.png", "Color y textura"),
                                    self._muestra("assets/img4.png", "Anuncio destacado"),
                                ],
                                spacing=18,
                                alignment=ft.MainAxisAlignment.CENTER,
                            ),
                            ft.Container(height=26),
                            ft.Row(
                                controls=[
                                    ft.Text(
                                        "Selecciona una referencia visual para continuar.",
                                        size=13,
                                        color="#8a7e72",
                                        italic=True,
                                        expand=True,
                                    ),
                                    ft.Container(
                                        content=ft.Row(
                                            controls=[
                                                ft.Icon(ft.Icons.AUTO_AWESOME, color="#ffa200", size=18),
                                                ft.Text("Continuar", color="#ffffff", size=14, weight="bold"),
                                            ],
                                            spacing=8,
                                        ),
                                        bgcolor="#0d0905",
                                        padding=ft.padding.symmetric(horizontal=24, vertical=13),
                                        border_radius=28,
                                        shadow=ft.BoxShadow(
                                            blur_radius=10,
                                            color=ft.Colors.with_opacity(0.28, ft.Colors.BLACK),
                                            offset=ft.Offset(0, 4),
                                        ),
                                        ink=True,
                                    ),
                                ],
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                        ],
                    ),
                ),
            ],
        )

    def _paso(self, numero: str, texto: str, activo: bool = False, completado: bool = False):
        return ft.Container(
            width=270,
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(
                            ft.Icons.CHECK,
                            color="#ffffff",
                            size=16,
                        ) if completado else ft.Text(
                            numero,
                            color="#ffffff",
                            size=14,
                            weight="bold",
                        ),
                        width=32,
                        height=32,
                        alignment=ft.Alignment(0, 0),
                        bgcolor="#7d8545" if completado else "#0d0905",
                        border_radius=16,
                    ),
                    ft.Text(
                        texto,
                        color="#1c1610" if activo else "#7c7267",
                        size=14,
                        weight="bold" if activo else "normal",
                        expand=True,
                    ),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor="#fbf5e9",
            border_radius=28,
            padding=ft.padding.symmetric(horizontal=14, vertical=9),
            shadow=ft.BoxShadow(
                blur_radius=10 if activo else 6,
                spread_radius=0,
                color=ft.Colors.with_opacity(0.20 if activo else 0.10, "#f4ca83"),
                offset=ft.Offset(0, 3),
            ),
        )

    def _pestana(self, texto: str, activa: bool):
        return ft.Container(
            content=ft.Text(
                texto,
                size=16,
                color="#1c1610" if activa else "#8a7e72",
                weight="bold" if activa else "normal",
            ),
            bgcolor="#f8f1de" if activa else "#f4edde",
            padding=ft.padding.symmetric(horizontal=18, vertical=10),
            border_radius=22,
            shadow=ft.BoxShadow(
                blur_radius=8,
                spread_radius=0,
                color=ft.Colors.with_opacity(0.22 if activa else 0.08, "#030303"),
                offset=ft.Offset(0, 3),
            ),
        )

    def _muestra(self, imagen: str, texto: str):
        return ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            controls=[
                ft.Container(
                    content=ft.Image(
                        src=imagen,
                        width=176,
                        height=198,
                        fit=ft.BoxFit.COVER,
                        border_radius=12,
                    ),
                    border_radius=14,
                    shadow=ft.BoxShadow(
                        blur_radius=10,
                        color=ft.Colors.with_opacity(0.22, ft.Colors.BLACK),
                        offset=ft.Offset(0, 4),
                    ),
                ),
                ft.Container(
                    width=24,
                    height=24,
                    border=ft.border.all(2, "#d9ad4e"),
                    border_radius=12,
                    bgcolor="#fbf5e9",
                ),
                ft.Text(texto, size=11, color="#806f61"),
            ],
        )
