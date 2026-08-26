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

FASE 3 (Cloudflare R2): el diálogo ahora también deja elegir una foto local,
la muestra en miniatura de preview ANTES de guardar, y al guardar la sube a
R2 (comprimida a WebP con models/cloudflare_storage.py) antes de mandar el
image_url a Supabase. El selector de archivo usa TKINTER, no el FilePicker
de Flet — pedido explícito del dueño ("nunca he logrado hechar a andar el
filepicker de flet"), ver _elegir_archivo_imagen() más abajo. Todo el
orden de reversa (subir antes de guardar, borrar la foto vieja/huérfana
solo después de que el guardado en Supabase ya salió bien) vive en
_guardar()/_eliminar_async() de esta clase — el detalle completo está en el
docstring de models/cloudflare_storage.py, que es quien de verdad sube/
borra en R2.

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
  - (Fase 3) El botón "Agregar/Cambiar foto" reusa el par neutro ya
    establecido para superficies de input (borde #eadfca / fondo #f8f1de)
    en forma de píldora — es la misma combinación que ya usan todos los
    campos de este mismo diálogo, aplicada a un botón en vez de a un
    TextField.
Si el dueño prefiere otra medida, es un cambio de una línea en este archivo.
"""
import asyncio
import tkinter as tk
from tkinter import filedialog

import flet as ft
import httpx

from models import cloudflare_storage
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


def _elegir_archivo_imagen() -> str | None:
    """Abre el selector de archivos NATIVO de Windows vía Tkinter — a
    pedido explícito del dueño en vez del FilePicker de Flet. Se crea una
    raíz de Tk oculta, se muestra el diálogo (bloqueante) y se destruye la
    raíz enseguida; el resto de la app sigue siendo 100% Flet, esto no deja
    ningún estado de Tkinter vivo. Devuelve la ruta elegida o None si el
    dueño cerró/canceló el diálogo.

    BLOQUEANTE de verdad (congela el hilo que la llama hasta que se cierra
    el diálogo) — SIEMPRE se invoca vía asyncio.to_thread desde
    _elegir_foto_async(), nunca directo desde un on_click, o congelaría
    también la ventana de Flet mientras el selector está abierto."""
    raiz = tk.Tk()
    raiz.withdraw()
    raiz.attributes("-topmost", True)  # que no se abra detrás de la ventana de Flet
    try:
        ruta = filedialog.askopenfilename(
            title="Selecciona una foto del platillo",
            filetypes=[
                ("Imágenes", "*.jpg *.jpeg *.png *.webp *.bmp"),
                ("Todos los archivos", "*.*"),
            ],
        )
    finally:
        raiz.destroy()
    return ruta or None


class DialogoPlatillo:
    """Construye y controla un ft.AlertDialog de alta/edición.

    Uso:
        DialogoPlatillo(router, on_guardado=callback, platillo=fila_o_None).abrir()

    `platillo=None` → modo alta ("Agregar platillo"). `platillo=<dict>` →
    modo edición, precargado con esa fila (agrega también el botón
    "Eliminar platillo"). `on_guardado` se llama después de
    crear/actualizar/eliminar con éxito, para que menu_view.py refresque
    la tabla — recibe UN argumento opcional (Fase 3): `None` en el caso
    normal, o un texto de aviso si de pasada falló borrar una foto vieja/
    huérfana en Cloudflare R2 (el guardado/borrado en Supabase YA salió
    bien cuando eso pasa; ver models/cloudflare_storage.py).
    """

    def __init__(self, router, on_guardado, platillo: dict | None = None):
        self.router = router
        self.page = router.page
        self.on_guardado = on_guardado
        self.editando = platillo is not None
        self.platillo = platillo or {}
        self._ocupado = False  # True mientras hay un guardado/borrado en curso
        self._eligiendo_foto = False  # True mientras el selector nativo está abierto

        # Fase 3 — estado de la foto. _ruta_imagen_nueva es un path LOCAL
        # (todavía no subido) que se llena solo si el dueño elige un
        # archivo nuevo en este diálogo; _imagen_url_actual es la image_url
        # que YA tenía la fila en Supabase (None si es alta, o si edita un
        # platillo que todavía cae al placeholder). Los dos nunca se pisan:
        # _guardar() decide qué subir/borrar mirando cuál de los dos trae
        # algo.
        self._ruta_imagen_nueva: str | None = None
        self._imagen_url_actual: str | None = (
            self.platillo.get("image_url") if self.editando else None
        )

        # ---------------- foto (Fase 3) ----------------
        self.imagen_preview = ft.Image(
            src=self._imagen_url_actual or "assets/taco.jpg",
            width=72,
            height=72,
            fit=ft.BoxFit.COVER,
            border_radius=12,
            # Si _imagen_url_actual ya no carga (borrada a mano, sin
            # internet), cae al mismo placeholder que usan las filas sin
            # foto en vez de un ícono roto.
            error_content=ft.Image(
                src="assets/taco.jpg", width=72, height=72, fit=ft.BoxFit.COVER, border_radius=12
            ),
        )
        self._texto_boton_foto = ft.Text(
            "Cambiar foto" if self._imagen_url_actual else "Agregar foto",
            color="#5e5449",
            weight="bold",
            size=13,
        )
        self.boton_foto = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ADD_A_PHOTO_OUTLINED, size=15, color="#5e5449"),
                    self._texto_boton_foto,
                ],
                spacing=6,
                tight=True,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            bgcolor="#f8f1de",
            border=ft.border.all(1, "#eadfca"),
            border_radius=30,
            padding=ft.padding.symmetric(horizontal=16, vertical=10),
            ink=True,
            on_click=self._on_elegir_foto_click,
        )
        self.fila_foto = ft.Row(
            controls=[
                self.imagen_preview,
                ft.Container(width=14),
                ft.Column(
                    controls=[
                        self.boton_foto,
                        ft.Text(
                            "JPG o PNG · se optimiza automáticamente",
                            size=11,
                            color="#8a7e72",
                        ),
                    ],
                    spacing=6,
                    tight=True,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

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
            self.fila_foto,
            ft.Container(height=14),
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
        self._set_cargando(True, "Guardando...")
        imagen_nueva_url = None  # URL en R2 de la foto recién subida, si hubo una

        # Fase 3 — paso 1: si el dueño eligió una foto nueva en este
        # diálogo, comprimirla y subirla ANTES de tocar Supabase (orden de
        # reversa pedido: subir primero, insertar/actualizar después — ver
        # models/cloudflare_storage.py).
        if self._ruta_imagen_nueva:
            self._set_cargando(True, "Optimizando imagen...")
            try:
                datos_webp = await asyncio.to_thread(
                    cloudflare_storage.validar_y_comprimir, self._ruta_imagen_nueva
                )
            except cloudflare_storage.ArchivoInvalido as e:
                self._mostrar_error(str(e))
                self._set_cargando(False)
                return
            except Exception as e:
                print(f"[dialogo_platillo] error inesperado al comprimir la imagen: {e}")
                self._mostrar_error("No se pudo procesar la foto. Intenta con otra imagen.")
                self._set_cargando(False)
                return

            self._set_cargando(True, "Subiendo foto...")
            try:
                imagen_nueva_url = await asyncio.to_thread(
                    cloudflare_storage.subir_imagen, datos_webp
                )
            except cloudflare_storage.SubidaFallida as e:
                print(f"[dialogo_platillo] {e}")
                self._mostrar_error(str(e) or "No se pudo subir la foto.")
                self._set_cargando(False)
                return

            datos["image_url"] = imagen_nueva_url
            self._set_cargando(True, "Guardando...")

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
            await self._revertir_imagen_si_hace_falta(imagen_nueva_url)
            self._mostrar_error("No hay conexión con el servidor. Revisa tu internet.")
            self._set_cargando(False)
            return
        except Exception as e:
            print(f"[dialogo_platillo] error al guardar: {e}")
            await self._revertir_imagen_si_hace_falta(imagen_nueva_url)
            self._mostrar_error("No se pudo guardar el platillo. Intenta de nuevo.")
            self._set_cargando(False)
            return

        # Fase 3 — paso 2: el guardado en Supabase YA salió bien. Si había
        # una foto VIEJA distinta de la nueva, es SEGURO borrarla ahora (la
        # fila ya quedó apuntando a la nueva) — orden de reversa igual que
        # EJEMPLOS/lilshop.html. Si esto falla, el platillo de todos modos
        # ya se guardó bien; solo se avisa que la limpieza no se pudo hacer
        # (ya quedó registrada como huérfano, ver cloudflare_storage.py).
        aviso_limpieza = None
        imagen_vieja = self.platillo.get("image_url") if self.editando else None
        if imagen_nueva_url and imagen_vieja and imagen_vieja != imagen_nueva_url:
            try:
                await asyncio.to_thread(cloudflare_storage.eliminar_imagen, imagen_vieja)
            except cloudflare_storage.LimpiezaImagenFallida:
                aviso_limpieza = (
                    "El platillo se guardó, pero no se pudo borrar su foto "
                    "anterior en Cloudflare. Quedó registrada para limpiarla después."
                )

        self._set_cargando(False)  # si no, _cerrar() se niega a cerrar (_ocupado sigue True)
        self._cerrar()
        self.on_guardado(aviso_limpieza)

    async def _revertir_imagen_si_hace_falta(self, imagen_nueva_url: str | None):
        """Si ya se había subido una imagen nueva a R2 pero el guardado en
        Supabase falló DESPUÉS, borra esa imagen para no dejar un huérfano
        de un platillo que nunca se guardó (orden de reversa pedido para la
        Fase 3). No se muestra un segundo error en pantalla si esta
        limpieza también falla: el error principal (que no se pudo
        guardar) es el que le importa ver al dueño, y el intento de borrado
        ya quedó registrado como huérfano de todos modos — ver
        models/cloudflare_storage.py."""
        if not imagen_nueva_url:
            return
        try:
            await asyncio.to_thread(cloudflare_storage.eliminar_imagen, imagen_nueva_url)
        except cloudflare_storage.LimpiezaImagenFallida:
            pass

    # ------------------------------------------------------------------
    # Foto (Fase 3): selector nativo de Tkinter + preview antes de guardar
    # ------------------------------------------------------------------
    def _on_elegir_foto_click(self, e):
        if self._ocupado or self._eligiendo_foto:
            return  # no abrir el selector a medio guardado/borrado, ni dos veces
        self.page.run_task(self._elegir_foto_async)

    async def _elegir_foto_async(self):
        self._eligiendo_foto = True
        self.boton_foto.disabled = True
        self.boton_foto.update()
        try:
            # _elegir_archivo_imagen() es bloqueante de verdad (el diálogo
            # nativo de Windows) — a un hilo aparte, o congelaría la
            # ventana de Flet mientras el dueño elige el archivo.
            ruta = await asyncio.to_thread(_elegir_archivo_imagen)
        finally:
            self._eligiendo_foto = False
            self.boton_foto.disabled = False
            self.boton_foto.update()

        if not ruta:
            return  # el dueño cerró/canceló el selector de archivos

        try:
            with open(ruta, "rb") as archivo:
                vista_previa = archivo.read()
        except OSError as e:
            print(f"[dialogo_platillo] no se pudo leer el archivo elegido: {e}")
            self._mostrar_error("No se pudo leer el archivo seleccionado.")
            return

        # La validación de verdad (¿es una imagen? ¿no pesa de más?) corre
        # en _guardar() vía validar_y_comprimir() — aquí solo se muestra la
        # miniatura tal cual para que el dueño la vea ANTES de guardar,
        # como pidió. Si el archivo fuera basura, error_content de
        # self.imagen_preview cae al placeholder en vez de un ícono roto.
        self._ruta_imagen_nueva = ruta
        self.imagen_preview.src = vista_previa
        self._texto_boton_foto.value = "Cambiar foto"
        self.imagen_preview.update()
        self._texto_boton_foto.update()

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
        self._set_cargando(True, "Eliminando...")
        # Se guarda ANTES del delete porque después self.platillo ya no
        # corresponde a ninguna fila real — PlatilloDAO.eliminar() no
        # regresa la fila borrada.
        imagen_a_borrar = self.platillo.get("image_url")
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

        # Fase 3 — la fila YA se borró de verdad (PlatilloDAO.eliminar() es
        # un DELETE real, ver CLAUDE.md). Ahora se borra su foto en R2, si
        # tenía una. Si esto falla, el platillo de todos modos ya se fue;
        # solo se avisa que la foto pudo quedar huérfana (ya quedó
        # registrada en huerfanos_r2.json de todos modos — ver
        # models/cloudflare_storage.py).
        aviso_limpieza = None
        if imagen_a_borrar:
            try:
                await asyncio.to_thread(cloudflare_storage.eliminar_imagen, imagen_a_borrar)
            except cloudflare_storage.LimpiezaImagenFallida:
                aviso_limpieza = (
                    "El platillo se eliminó, pero no se pudo borrar su foto "
                    "en Cloudflare. Quedó registrada para limpiarla después."
                )

        self._set_cargando(False)  # si no, _cerrar() se niega a cerrar (_ocupado sigue True)
        self._cerrar()
        self.on_guardado(aviso_limpieza)

    # ------------------------------------------------------------------
    def _mostrar_error(self, mensaje: str):
        self.texto_error.value = mensaje
        self.zona_error.visible = True
        self.zona_error.update()

    def _set_cargando(self, cargando: bool, texto: str = "Guardando..."):
        """`texto` (Fase 3) es el paso actual mientras `cargando=True` —
        _guardar() lo va cambiando ("Optimizando imagen..." → "Subiendo
        foto..." → "Guardando...") porque ahora puede haber DOS operaciones
        lentas seguidas (Pillow + la subida) antes de tocar Supabase, y el
        dueño pidió ver en qué paso va. Se ignora cuando cargando=False."""
        self._ocupado = cargando
        self.boton_guardar.disabled = cargando
        self.boton_guardar.content = (
            ft.Row(
                controls=[
                    ft.ProgressRing(width=18, height=18, stroke_width=2, color="#f4ca83"),
                    ft.Text(texto, color="#ffffff", weight="bold", size=14),
                ],
                spacing=10,
                alignment=ft.MainAxisAlignment.CENTER,
            )
            if cargando
            else self._texto_boton_guardar
        )
        self.boton_guardar.update()
        if self.boton_eliminar is not None:
            self.boton_eliminar.disabled = cargando
            self.boton_eliminar.update()
        # Fase 3: tampoco se debe poder abrir el selector de archivos a
        # medio guardado/borrado.
        self.boton_foto.disabled = cargando
        self.boton_foto.update()


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
