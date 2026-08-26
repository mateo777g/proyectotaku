"""
views/components/dialogo_platillo.py
Ventana de alta/edición de un platillo (Fase 2.6) — se abre desde el botón
"Agregar platillo" y desde el lápiz de cada fila de menu_view.py.

Es pantalla NUEVA, así que se construye con el mismo lenguaje visual que
sesion_view.py (Fase 2.0): tarjeta ancho 420, campos height=52/border_radius=16
con #eadfca/#f4ca83, botón oscuro border_radius=30, y la misma caja de error
roja (#f7e4e3/#d9534f/#a33c39) que ya usan sesion_view.py y menu_view.py.

El gotcha de Flet que quedó anotado en la Fase 2.0 aplica igual aquí: el
Column de adentro de la tarjeta necesita tight=True, si no reclama todo el
alto disponible del AlertDialog en vez de solo el que pide su contenido.

NADA de imágenes aquí — image_url no se toca, sigue cayendo a
assets/taco.jpg hasta la Fase 3 (Cloudflare).

Dos decisiones visuales que no tenían precedente exacto en el proyecto y que
se resolvieron reusando piezas ya existentes en vez de inventar:
  - El tamaño del título del diálogo (26) es un punto medio entre los ~40-48
    de un título de página y los ~15-19 de texto en línea que define
    CLAUDE.md — no hay un tercer tamaño de "título de modal" definido.
  - El botón "Eliminar platillo" reusa tal cual el par de colores de la caja
    de error del proyecto (#f7e4e3 fondo / #d9534f borde / #a33c39 texto)
    para su variante de contorno, y #d9534f sólido para el de confirmación
    ("Sí, eliminar") — es el color de "destructivo" que ya define la paleta,
    aplicado a un botón en vez de a un badge.
Si el dueño prefiere otra medida, es un cambio de una línea en este archivo.
"""
import asyncio

import flet as ft
import httpx

from models.platillo_dao import PlatilloDAO

_CATEGORIAS = ["Platillos", "Bebidas", "Postres"]

# Mismo ancho de tarjeta y campo que sesion_view.py (Fase 2.0) — se reusa la
# medida ya establecida en vez de inventar una nueva.
_ANCHO_TARJETA = 420
_ANCHO_CAMPO = _ANCHO_TARJETA - 36 - 36


def _texto_precio(valor) -> str:
    """precio llega como numeric(10,2) de Supabase (float en Python). Se
    precarga sin decimales de sobra en el campo de edición, mismo criterio
    que _formatear_precio() de menu_view.py."""
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return ""
    if numero.is_integer():
        return str(int(numero))
    return f"{numero:.2f}"


class DialogoPlatillo:
    """Construye y controla un ft.AlertDialog de alta/edición.

    Uso:
        DialogoPlatillo(router, on_guardado=callback, platillo=fila_o_None).abrir()

    `platillo=None` → modo alta ("Agregar platillo"). `platillo=<dict>` →
    modo edición, precargado con esa fila (agrega también el botón
    "Eliminar platillo"). `on_guardado` se llama sin argumentos después de
    crear/actualizar/eliminar con éxito, para que menu_view.py refresque
    la tabla.
    """

    def __init__(self, router, on_guardado, platillo: dict | None = None):
        self.router = router
        self.page = router.page
        self.on_guardado = on_guardado
        self.editando = platillo is not None
        self.platillo = platillo or {}
        self._ocupado = False  # True mientras hay un guardado/borrado en curso

        # ---------------- campos ----------------
        self.campo_nombre = ft.TextField(
            value=self.platillo.get("nombre", ""),
            hint_text="Nombre del platillo",
            prefix_icon=ft.Icons.RESTAURANT_MENU_OUTLINED,
            autofocus=True,
            width=_ANCHO_CAMPO,
            height=52,
            border_radius=16,
            border_color="#eadfca",
            focused_border_color="#f4ca83",
            bgcolor="#f8f1de",
            color="#5e5449",
            hint_style=ft.TextStyle(color="#9b8f7e"),
            text_size=14,
        )

        self.campo_descripcion = ft.TextField(
            value=self.platillo.get("descripcion") or "",
            hint_text="Descripción (opcional)",
            prefix_icon=ft.Icons.NOTES_OUTLINED,
            multiline=True,
            min_lines=2,
            max_lines=3,
            width=_ANCHO_CAMPO,
            border_radius=16,
            border_color="#eadfca",
            focused_border_color="#f4ca83",
            bgcolor="#f8f1de",
            color="#5e5449",
            hint_style=ft.TextStyle(color="#9b8f7e"),
            text_size=14,
        )

        self.campo_categoria = ft.Dropdown(
            value=self.platillo.get("categoria") or None,
            hint_text="Selecciona una categoría",
            leading_icon=ft.Icons.CATEGORY_OUTLINED,
            options=[ft.DropdownOption(key=c, text=c) for c in _CATEGORIAS],
            width=_ANCHO_CAMPO,
            height=52,
            border_radius=16,
            border_color="#eadfca",
            focused_border_color="#f4ca83",
            filled=True,
            fill_color="#f8f1de",
            color="#5e5449",
            hint_style=ft.TextStyle(color="#9b8f7e"),
            text_size=14,
        )

        self.campo_precio = ft.TextField(
            value=_texto_precio(self.platillo.get("precio")),
            hint_text="Precio",
            prefix="$ ",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=_ANCHO_CAMPO,
            height=52,
            border_radius=16,
            border_color="#eadfca",
            focused_border_color="#f4ca83",
            bgcolor="#f8f1de",
            color="#5e5449",
            hint_style=ft.TextStyle(color="#9b8f7e"),
            text_size=14,
        )

        # ---------------- caja de error (copiada de sesion_view.py) ----------------
        self.texto_error = ft.Text("", size=12, color="#a33c39", expand=True)
        self.zona_error = ft.Container(
            visible=False,
            width=_ANCHO_CAMPO,
            bgcolor="#f7e4e3",
            border=ft.border.all(1, "#d9534f"),
            border_radius=12,
            padding=ft.padding.symmetric(horizontal=12, vertical=10),
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE, size=15, color="#d9534f"),
                    self.texto_error,
                ],
                spacing=8,
            ),
        )

        # ---------------- botón guardar (mismo lenguaje que "Entrar") ----------------
        self._texto_boton_guardar = ft.Text(
            "Guardar cambios" if self.editando else "Agregar platillo",
            color="#ffffff",
            weight="bold",
            size=16,
        )
        self.boton_guardar = ft.Container(
            content=self._texto_boton_guardar,
            alignment=ft.Alignment(0, 0),
            bgcolor="#0d0905",
            border_radius=30,
            width=_ANCHO_CAMPO,
            padding=ft.padding.symmetric(vertical=16),
            ink=True,
            on_click=self._on_guardar_click,
        )

        controles_tarjeta = [
            ft.Text(
                "EDITAR PLATILLO" if self.editando else "AGREGAR PLATILLO",
                size=11,
                weight="bold",
                color="#b58a6d",
                text_align=ft.TextAlign.CENTER,
            ),
            ft.Text(
                self.platillo.get("nombre") if self.editando else "Nuevo platillo",
                size=26,
                font_family="Georgia",
                italic=True,
                color="#18120d",
                text_align=ft.TextAlign.CENTER,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
            ft.Container(height=24),
            self.campo_nombre,
            ft.Container(height=14),
            self.campo_descripcion,
            ft.Container(height=14),
            self.campo_categoria,
            ft.Container(height=14),
            self.campo_precio,
            self.zona_error,
            ft.Container(height=22),
            self.boton_guardar,
        ]

        self.boton_eliminar = None
        if self.editando:
            self.boton_eliminar = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.DELETE_OUTLINE, size=16, color="#a33c39"),
                        ft.Text(
                            "Eliminar platillo", color="#a33c39", weight="bold", size=14
                        ),
                    ],
                    spacing=8,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                bgcolor="#f7e4e3",
                border=ft.border.all(1, "#d9534f"),
                border_radius=30,
                width=_ANCHO_CAMPO,
                padding=ft.padding.symmetric(vertical=14),
                ink=True,
                on_click=self._on_eliminar_click,
            )
            controles_tarjeta += [ft.Container(height=10), self.boton_eliminar]

        # Botón de cerrar (X) — modal=True bloquea el tap fuera del diálogo
        # y Flet no le da Escape por default, así que sin esto no había
        # ninguna forma de cancelar el formulario sin guardar o eliminar.
        # Mismo lenguaje que los íconos de acción de menu_view.py
        # (30x30, border_radius=15, ink=True, #756b5e).
        self.boton_cerrar = ft.Container(
            content=ft.Icon(ft.Icons.CLOSE, size=16, color="#756b5e"),
            width=30,
            height=30,
            border_radius=15,
            ink=True,
            alignment=ft.Alignment(0, 0),
            on_click=lambda e: self._cerrar(),
            top=12,
            right=12,
            tooltip="Cerrar",
        )

        self.dialog = ft.AlertDialog(
            modal=True,
            bgcolor="#f8f1de",
            shape=ft.RoundedRectangleBorder(radius=16),
            content_padding=ft.padding.symmetric(horizontal=36, vertical=36),
            content=ft.Stack(
                controls=[
                    ft.Container(
                        width=_ANCHO_TARJETA - 72,
                        content=ft.Column(
                            # Mismo gotcha que sesion_view.py: sin tight=True
                            # el Column reclama todo el alto disponible del
                            # diálogo.
                            tight=True,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=0,
                            scroll=ft.ScrollMode.AUTO,
                            controls=controles_tarjeta,
                        ),
                    ),
                    self.boton_cerrar,
                ],
            ),
        )

    # ------------------------------------------------------------------
    def abrir(self):
        self.page.show_dialog(self.dialog)

    def _cerrar(self):
        if self._ocupado:
            return  # hay un guardado/borrado en curso, no se cancela a medias
        self.page.pop_dialog()

    # ------------------------------------------------------------------
    def _validar(self):
        """Valida en el formulario ANTES de mandar a Supabase, para que el
        error se vea con el estilo del proyecto y no como un error crudo de
        Postgres — los CHECK de la tabla (categoria in (...), precio >= 0)
        son el respaldo final, no la primera línea de defensa."""
        nombre = (self.campo_nombre.value or "").strip()
        if not nombre:
            return None, "El nombre del platillo es obligatorio."

        categoria = self.campo_categoria.value
        if categoria not in _CATEGORIAS:
            return None, "Selecciona una categoría."

        precio_texto = (self.campo_precio.value or "").strip().replace(",", "")
        try:
            precio = float(precio_texto)
        except ValueError:
            return None, "El precio debe ser un número (ej. 145 o 145.50)."
        if precio < 0:
            return None, "El precio no puede ser negativo."

        datos = {
            "nombre": nombre,
            "descripcion": (self.campo_descripcion.value or "").strip(),
            "categoria": categoria,
            "precio": precio,
        }
        return datos, None

    def _on_guardar_click(self, e):
        datos, error = self._validar()
        if error:
            self._mostrar_error(error)
            return
        self.page.run_task(self._guardar, datos)

    async def _guardar(self, datos: dict):
        self._set_cargando(True)
        try:
            if self.editando:
                # actualizar()/crear() son bloqueantes (supabase-py es
                # síncrono) — se mandan a un hilo aparte, igual que
                # sign_in_with_password en sesion_view.py.
                await asyncio.to_thread(
                    PlatilloDAO.actualizar, self.platillo["id"], datos
                )
            else:
                await asyncio.to_thread(PlatilloDAO.crear, datos)
        except httpx.RequestError as e:
            print(f"[dialogo_platillo] error de red al guardar: {e}")
            self._mostrar_error("No hay conexión con el servidor. Revisa tu internet.")
            self._set_cargando(False)
            return
        except Exception as e:
            print(f"[dialogo_platillo] error al guardar: {e}")
            self._mostrar_error("No se pudo guardar el platillo. Intenta de nuevo.")
            self._set_cargando(False)
            return

        self._set_cargando(False)  # si no, _cerrar() se niega a cerrar (_ocupado sigue True)
        self._cerrar()
        self.on_guardado()

    # ------------------------------------------------------------------
    def _on_eliminar_click(self, e):
        _confirmar(
            self.page,
            titulo="¿Eliminar este platillo?",
            mensaje=(
                f"\"{self.platillo.get('nombre', '')}\" se borrará por completo "
                "de Supabase. Esta acción no se puede deshacer."
            ),
            on_confirmar=lambda: self.page.run_task(self._eliminar_async),
        )

    async def _eliminar_async(self):
        self._set_cargando(True)
        try:
            await asyncio.to_thread(PlatilloDAO.eliminar, self.platillo["id"])
        except httpx.RequestError as e:
            print(f"[dialogo_platillo] error de red al eliminar: {e}")
            self._mostrar_error("No hay conexión con el servidor. Revisa tu internet.")
            self._set_cargando(False)
            return
        except Exception as e:
            print(f"[dialogo_platillo] error al eliminar: {e}")
            self._mostrar_error("No se pudo eliminar el platillo. Intenta de nuevo.")
            self._set_cargando(False)
            return

        self._set_cargando(False)  # si no, _cerrar() se niega a cerrar (_ocupado sigue True)
        self._cerrar()
        self.on_guardado()

    # ------------------------------------------------------------------
    def _mostrar_error(self, mensaje: str):
        self.texto_error.value = mensaje
        self.zona_error.visible = True
        self.zona_error.update()

    def _set_cargando(self, cargando: bool):
        self._ocupado = cargando
        self.boton_guardar.disabled = cargando
        self.boton_guardar.content = (
            ft.ProgressRing(width=18, height=18, stroke_width=2, color="#f4ca83")
            if cargando
            else self._texto_boton_guardar
        )
        self.boton_guardar.update()
        if self.boton_eliminar is not None:
            self.boton_eliminar.disabled = cargando
            self.boton_eliminar.update()


def _confirmar(page: ft.Page, *, titulo: str, mensaje: str, on_confirmar):
    """Diálogo de confirmación genérico para acciones destructivas (aquí,
    eliminar un platillo). Mismo lenguaje visual que el resto del proyecto:
    tarjeta #f8f1de/#eadfca, ícono de alerta, botón rojo #d9534f para la
    acción irreversible y uno con borde neutro para cancelar."""

    def _cerrar(e=None):
        page.pop_dialog()

    def _confirmar_click(e):
        _cerrar()
        on_confirmar()

    dialogo = ft.AlertDialog(
        modal=True,
        bgcolor="#f8f1de",
        shape=ft.RoundedRectangleBorder(radius=16),
        content_padding=ft.padding.symmetric(horizontal=32, vertical=32),
        content=ft.Container(
            width=340,
            content=ft.Column(
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=0,
                controls=[
                    ft.Icon(ft.Icons.WARNING_AMBER_OUTLINED, size=30, color="#d9534f"),
                    ft.Container(height=12),
                    ft.Text(
                        titulo,
                        size=17,
                        font_family="Georgia",
                        italic=True,
                        weight="bold",
                        color="#18120d",
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=8),
                    ft.Text(
                        mensaje,
                        size=13,
                        color="#7c7267",
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=24),
                    ft.Container(
                        content=ft.Text(
                            "Sí, eliminar", color="#ffffff", weight="bold", size=14
                        ),
                        alignment=ft.Alignment(0, 0),
                        bgcolor="#d9534f",
                        border_radius=30,
                        width=268,
                        padding=ft.padding.symmetric(vertical=14),
                        ink=True,
                        on_click=_confirmar_click,
                    ),
                    ft.Container(height=10),
                    ft.Container(
                        content=ft.Text(
                            "Cancelar", color="#5e5449", weight="bold", size=14
                        ),
                        alignment=ft.Alignment(0, 0),
                        bgcolor=ft.Colors.TRANSPARENT,
                        border=ft.border.all(1, "#eadfca"),
                        border_radius=30,
                        width=268,
                        padding=ft.padding.symmetric(vertical=14),
                        ink=True,
                        on_click=_cerrar,
                    ),
                ],
            ),
        ),
    )
    page.show_dialog(dialogo)
