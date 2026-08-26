import datetime

import flet as ft


class AjustesView(ft.Container):
    def __init__(self, router):
        super().__init__()
        self.router = router
        self.expand = True
        self.height = float("inf")
        self.bgcolor = "#fbf5e9"
        self.padding = ft.padding.only(left=36, right=36, top=42, bottom=36)

        dias = ["LUNES", "MARTES", "MIÉRCOLES", "JUEVES", "VIERNES", "SÁBADO", "DOMINGO"]
        meses = [
            "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
            "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE",
        ]
        hoy = datetime.datetime.now()
        fecha_texto = f"{dias[hoy.weekday()]}, {hoy.day} DE {meses[hoy.month - 1]}"

        self.ruta_exportacion = ft.TextField(
            value="C:\\Users\\Angel\\Downloads",
            height=54,
            expand=True,
            border=ft.InputBorder.OUTLINE,
            border_radius=14,
            border_color="#eadfca",
            focused_border_color="#f4ca83",
            bgcolor="#fbf5e9",
            color="#1c1610",
            text_size=14,
            content_padding=ft.padding.symmetric(horizontal=16, vertical=14),
        )

        self.content = ft.Column(
            expand=True,
            height=float("inf"),
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.Text(fecha_texto, size=13, weight="bold", color="#b58a6d"),
                ft.Text(
                    "Ajustes",
                    size=42,
                    font_family="Georgia",
                    italic=True,
                    color="#18120d",
                ),
                ft.Text(
                    "Configura dónde se guardará el contenido que generes.",
                    size=15,
                    color="#7c7267",
                ),
                ft.Container(height=30),
                ft.Container(
                    bgcolor="#f8f1de",
                    border_radius=24,
                    padding=ft.padding.only(left=28, right=28, top=28, bottom=28),
                    shadow=ft.BoxShadow(
                        blur_radius=18,
                        spread_radius=0,
                        color=ft.Colors.with_opacity(0.22, "#f4ca83"),
                        offset=ft.Offset(0, 6),
                    ),
                    content=ft.Column(
                        spacing=0,
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Container(
                                        content=ft.Icon(ft.Icons.FOLDER_OUTLINED, color="#c86a28", size=22),
                                        width=44,
                                        height=44,
                                        alignment=ft.Alignment(0, 0),
                                        bgcolor="#f4ca83",
                                        border_radius=22,
                                    ),
                                    ft.Column(
                                        expand=True,
                                        spacing=2,
                                        controls=[
                                            ft.Text(
                                                "Exportaciones locales",
                                                size=22,
                                                font_family="Georgia",
                                                weight="bold",
                                                italic=True,
                                                color="#1c1610",
                                            ),
                                            ft.Text(
                                                "Define la carpeta donde se guardarán tus imágenes y publicaciones.",
                                                size=13,
                                                color="#7c7267",
                                            ),
                                        ],
                                    ),
                                ],
                                spacing=14,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.Container(height=26),
                            ft.Divider(height=1, color="#eadfca"),
                            ft.Container(height=24),
                            ft.Text(
                                "Ruta para exportar contenido",
                                size=14,
                                weight="bold",
                                color="#1c1610",
                            ),
                            ft.Container(height=8),
                            ft.Row(
                                controls=[
                                    self.ruta_exportacion,
                                    ft.Container(
                                        content=ft.Icon(ft.Icons.FOLDER_OPEN_OUTLINED, color="#c86a28", size=24),
                                        width=54,
                                        height=54,
                                        alignment=ft.Alignment(0, 0),
                                        border_radius=27,
                                        ink=True,
                                    ),
                                ],
                                spacing=12,
                            ),
                            ft.Container(height=30),
                            ft.Row(
                                controls=[
                                    ft.Text(
                                        "Elige una carpeta accesible desde esta computadora.",
                                        size=12,
                                        color="#8a7e72",
                                        italic=True,
                                        expand=True,
                                    ),
                                    ft.Container(
                                        content=ft.Row(
                                            controls=[
                                                ft.Icon(ft.Icons.SAVE_OUTLINED, color="#ffa200", size=18),
                                                ft.Text("Guardar ajustes", color="#ffffff", size=14, weight="bold"),
                                            ],
                                            spacing=8,
                                        ),
                                        bgcolor="#0d0905",
                                        padding=ft.padding.symmetric(horizontal=22, vertical=13),
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
