import flet as ft


class AgenteIAView(ft.Container):
    def __init__(self, router):
        super().__init__()
        self.router = router
        self.expand = True
        self.height = float("inf")
        self.bgcolor = "#fbf5e9"
        self.padding = ft.padding.only(left=36, right=36, top=42, bottom=36)

        self.mensajes = ft.Column(
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.entrada = ft.TextField(
            hint_text="Escribe una pregunta sobre tu negocio...",
            height=64,
            expand=True,
            border=ft.InputBorder.NONE,
            bgcolor="#f8f1de",
            color="#1c1610",
            hint_style=ft.TextStyle(color="#8a7e72", size=15),
            text_size=15,
            content_padding=ft.padding.symmetric(horizontal=24, vertical=18),
            on_submit=self._enviar_mensaje,
        )

        caja_entrada = ft.Container(
            content=self.entrada,
            width=720,
            height=70,
            bgcolor="#f8f1de",
            border_radius=35,
            shadow=ft.BoxShadow(
                blur_radius=24,
                spread_radius=1,
                color=ft.Colors.with_opacity(0.30, ft.Colors.BLACK),
                offset=ft.Offset(0, 7),
            ),
        )

        contenido_centrado = ft.Column(
            controls=[
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                "Hola, Ary.",
                                size=40,
                                font_family="Georgia",
                                italic=True,
                                color="#18120d",
                            ),
                            ft.Text(
                                "¿En qué puedo ayudarte hoy?",
                                size=40,
                                font_family="Georgia",
                                italic=True,
                                color="#bf571d",
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=0,
                    ),
                    margin=ft.margin.only(bottom=34),
                ),
                self.mensajes,
                caja_entrada,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=0,
        )

        self.content = ft.Container(
            expand=True,
            alignment=ft.Alignment(0, 0),
            content=contenido_centrado,
        )

    def _enviar_mensaje(self, evento):
        texto = self.entrada.value.strip()
        if not texto:
            return

        self.mensajes.controls.append(
            ft.Container(
                content=ft.Text(texto, size=14, color="#1c1610"),
                bgcolor="#f4ca83",
                padding=ft.padding.symmetric(horizontal=18, vertical=10),
                border_radius=20,
            )
        )
        self.entrada.value = ""
        self.update()
