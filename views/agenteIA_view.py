import asyncio

import flet as ft

from models.ia_controller import IAController


class AgenteIAView(ft.Container):
    def __init__(self, router):
        super().__init__()
        self.router = router
        self.expand = True
        self.height = float("inf")
        self.bgcolor = "#fbf5e9"
        self.padding = ft.padding.only(left=36, right=36, top=42, bottom=36)

        # El controlador se crea perezosamente en el primer mensaje (ver
        # _responder) en vez de aquí, para que un OPENAI_API_KEY faltante en
        # el .env no reviente la vista al abrir Agente IA — se muestra como
        # una burbuja de error normal, igual que cualquier otro fallo de
        # conexión, y el dueño puede seguir viendo el resto del panel.
        self._ia: IAController | None = None
        # Conversación previa de esta sesión de chat (se pierde al navegar
        # fuera y volver, igual que cualquier otro estado de vista en este
        # proyecto — ninguna vista guarda nada entre visitas) — le da al
        # agente memoria de lo que ya se preguntó. Ver IAController.preguntar().
        self._historial: list[dict] = []
        self._procesando = False

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

    def _burbuja_usuario(self, texto: str) -> ft.Container:
        return ft.Container(
            content=ft.Text(texto, size=14, color="#1c1610"),
            bgcolor="#f4ca83",
            padding=ft.padding.symmetric(horizontal=18, vertical=10),
            border_radius=20,
        )

    def _burbuja_ia(self, texto: str) -> ft.Container:
        # Misma forma que la burbuja del usuario (mismo border_radius=20,
        # mismo padding) pero con los colores de superficie de tarjeta que
        # ya usa el resto del panel (#f8f1de/#eadfca), para distinguirla de
        # la burbuja dorada del usuario sin inventar una paleta nueva.
        # selectable=True porque las respuestas suelen traer cifras/precios
        # que el dueño va a querer copiar.
        return ft.Container(
            content=ft.Text(texto, size=14, color="#1c1610", selectable=True),
            bgcolor="#f8f1de",
            border=ft.border.all(1, "#eadfca"),
            padding=ft.padding.symmetric(horizontal=18, vertical=10),
            border_radius=20,
        )

    def _burbuja_pensando(self) -> ft.Row:
        # Mismo lenguaje visual de "cargando" que menu_view.py/home_view.py:
        # ProgressRing dorado + texto gris, solo que aquí en fila porque no
        # hay una tarjeta que envolver.
        return ft.Row(
            controls=[
                ft.ProgressRing(width=16, height=16, stroke_width=2, color="#f4ca83"),
                ft.Text("Pensando...", size=13, color="#8a7e72"),
            ],
            spacing=8,
            alignment=ft.MainAxisAlignment.CENTER,
        )

    def _burbuja_error(self, mensaje: str) -> ft.Container:
        # Mismo banner rojo #f7e4e3/#d9534f/#a33c39 que ya usan
        # menu_view.py/sesion_view.py para errores.
        return ft.Container(
            bgcolor="#f7e4e3",
            border=ft.border.all(1, "#d9534f"),
            border_radius=12,
            padding=ft.padding.symmetric(horizontal=16, vertical=10),
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE, size=15, color="#d9534f"),
                    ft.Text(mensaje, size=13, color="#a33c39"),
                ],
                spacing=8,
            ),
        )

    def _enviar_mensaje(self, evento):
        if self._procesando:
            return
        texto = self.entrada.value.strip()
        if not texto:
            return

        self.mensajes.controls.append(self._burbuja_usuario(texto))
        self.entrada.value = ""
        self.update()
        self.router.page.run_task(self._responder, texto)

    async def _responder(self, pregunta: str):
        self._procesando = True
        self.entrada.disabled = True
        indicador = self._burbuja_pensando()
        self.mensajes.controls.append(indicador)
        self.update()

        try:
            if self._ia is None:
                self._ia = IAController()
            respuesta = await asyncio.to_thread(
                self._ia.preguntar, pregunta, self._historial
            )
            self.mensajes.controls.remove(indicador)
            self.mensajes.controls.append(self._burbuja_ia(respuesta))
            # Solo se guarda en el historial DESPUÉS de una respuesta exitosa
            # — si la llamada falló, no queremos que una pregunta sin
            # respuesta quede colada en la conversación que se le manda al
            # modelo la próxima vez.
            self._historial.append({"role": "user", "content": pregunta})
            self._historial.append({"role": "assistant", "content": respuesta})
        except RuntimeError as error:
            # Típicamente el OPENAI_API_KEY faltante — ver IAController.__init__.
            self.mensajes.controls.remove(indicador)
            self.mensajes.controls.append(self._burbuja_error(str(error)))
        except Exception:
            self.mensajes.controls.remove(indicador)
            self.mensajes.controls.append(
                self._burbuja_error(
                    "No se pudo conectar con el agente de IA. Intenta de nuevo."
                )
            )
        finally:
            self._procesando = False
            self.entrada.disabled = False
            self.update()
