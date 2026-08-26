import datetime

import flet as ft


class BibliotecaView(ft.Container):
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

        self.content = ft.Column(
            expand=True,
            height=float("inf"),
            spacing=0,
            controls=[
                ft.Text(fecha_texto, size=13, weight="bold", color="#b58a6d"),
                ft.Text(
                    "Mi biblioteca",
                    size=42,
                    font_family="Georgia",
                    italic=True,
                    color="#18120d",
                ),
                ft.Text(
                    "Guarda y organiza el contenido que creas para tu negocio.",
                    size=15,
                    color="#7c7267",
                ),
                ft.Container(height=34),
                ft.Container(
                    expand=True,
                    bgcolor="#f8f1de",
                    border_radius=24,
                    shadow=ft.BoxShadow(
                        blur_radius=20,
                        spread_radius=0,
                        color=ft.Colors.with_opacity(0.20, "#f4ca83"),
                        offset=ft.Offset(0, 6),
                    ),
                    alignment=ft.Alignment(0, 0),
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=12,
                        controls=[
                            ft.Text(
                                "Tu biblioteca está vacía",
                                size=25,
                                font_family="Georgia",
                                weight="bold",
                                italic=True,
                                color="#1c1610",
                            ),
                            ft.Text(
                                "Aquí aparecerán tus publicaciones y materiales generados.",
                                size=14,
                                color="#7c7267",
                                text_align=ft.TextAlign.CENTER,
                            ),
                            ft.Container(height=8),
                            ft.Container(
                                width=230,
                                content=ft.Row(
                                    controls=[
                                        ft.Icon(ft.Icons.AUTO_AWESOME, color="#f4ca83", size=18),
                                        ft.Text("Crear contenido", color="#ffffff", size=14, weight="bold"),
                                    ],
                                    alignment=ft.MainAxisAlignment.CENTER,
                                    spacing=8,
                                ),
                                bgcolor="#0d0905",
                                padding=ft.padding.symmetric(horizontal=18, vertical=11),
                                border_radius=26,
                                shadow=ft.BoxShadow(
                                    blur_radius=10,
                                    color=ft.Colors.with_opacity(0.28, ft.Colors.BLACK),
                                    offset=ft.Offset(0, 4),
                                ),
                                ink=True,
                                on_click=lambda _: self.router.cambiar_vista("contenido"),
                            ),
                        ],
                    ),
                ),
            ],
        )
