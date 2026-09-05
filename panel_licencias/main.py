"""
panel_licencias/main.py — MI panel de licencias.  Se corre:

    python panel_licencias/main.py

QUÉ ES: el panel del DESARROLLADOR para administrar la licencia de TODOS los
clientes a la vez. Se conecta a los N proyectos de Supabase de la lista de
clientes (cada cliente = su propio proyecto, con su propia tabla
public.configuracion_negocio de un solo renglón) y los pinta en una tabla,
para ponerles fechas y prender/apagar `activo` cuando se les acabe el pago.

QUÉ NO ES:
  · No es el panel del dueño de un negocio. Ese es main.py, en la raíz.
  · No da de alta clientes. Crear el proyecto de Supabase de un cliente nuevo,
    correr su schema y crear su usuario de licencias es trabajo aparte, a
    mano. Este panel SOLO IMPORTA clientes que ya existen (los que estén
    escritos en clientes.json).
  · No tiene login. Corre en la compu del desarrollador y ya; el riesgo de que
    alguien la agarre desbloqueada está asumido a propósito.

AUTOCONTENIDO A PROPÓSITO: esta carpeta no importa NADA de models/, views/ ni
controllers/ del repo de Taku Monky — se va a sacar de aquí y tiene que seguir
corriendo tal cual. Sus únicas dependencias son las mismas del requirements.txt
(flet, supabase, httpx).

CREDENCIALES: no viven aquí. Viven en %LOCALAPPDATA%\\PanelLicencias\\clientes.json,
fuera del repo (que es público). Ver panel_licencias/clientes.py.

CADA FILA CARGA Y FALLA SOLA: los logins se hacen EN PARALELO (asyncio.gather
sobre asyncio.to_thread — en serie, 10 clientes se vuelven una eternidad; en
paralelo 6 tardan casi lo mismo que 1), y cada fila atrapa sus propios errores.
Un proyecto pausado, sin internet o con la contraseña mal puesta enseña su
error en SU renglón y los demás siguen vivos. Mismo criterio que las tarjetas
de views/home_view.py.
"""
import asyncio
import sys
from datetime import date, datetime
from pathlib import Path

import flet as ft

# Para poder correrlo como `python panel_licencias/main.py` y también como
# `python -m panel_licencias.main` sin cambiar los imports de abajo.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from clientes import RUTA_CLIENTES, ArchivoDeClientesInvalido, cargar_clientes  # noqa: E402
from conexion import conectar, traducir_error  # noqa: E402
from licencia_dao import ConfiguracionNegocioDAO  # noqa: E402

# Paleta neutra gris/negra, misma familia "zinc" que mesas.css: esto es MI
# producto, no la marca crema/dorada de Taku Monky. (La heredó de
# licencia_admin.py, el panel de licencia viejo que este reemplazó y que se
# borró el 2026-09-05.)
FONDO = "#f4f4f5"
SUPERFICIE = "#ffffff"
ENCABEZADO = "#e4e4e7"
BORDE = "#e4e4e7"
OSCURO = "#18181b"
TEXTO = "#27272a"
TENUE = "#71717a"
VERDE = "#16a34a"
ROJO = "#dc2626"
AMBAR = "#b45309"

_FORMATO_FECHA = "%Y-%m-%d"

# Pesos de las columnas. El encabezado y cada fila usan LOS MISMOS números, si
# no se desalinean (mismo trato que la tabla de views/menu_view.py).
_W_NEGOCIO = 3
_W_RESTO = 8  # ancho del bloque INICIO+FIN+RESTAN+ESTADO+acciones
_W_CELDA = 2
_W_ACCIONES = 48


def _fecha_valida(texto: str) -> bool:
    try:
        datetime.strptime(texto, _FORMATO_FECHA)
        return True
    except ValueError:
        return False


def _plural_dias(n: int) -> str:
    return "1 día" if n == 1 else f"{n} días"


def _texto_restan(fecha_fin) -> tuple[str, str]:
    """(texto, color) de la columna RESTAN, calculado al vuelo desde fecha_fin.

    NADA de esto lo calcula la base: las fechas son de referencia y la
    licencia NO se vence sola — `activo` es lo único que manda. Este texto
    existe justo para avisar cuándo hay que ir a apagar el switch a mano.
    """
    if not fecha_fin:
        return "—", TENUE
    try:
        fin = datetime.strptime(str(fecha_fin), _FORMATO_FECHA).date()
    except ValueError:
        return "fecha inválida", ROJO

    dias = (fin - date.today()).days
    if dias == 0:
        return "vence hoy", ROJO
    if dias < 0:
        return f"vencido hace {_plural_dias(-dias)}", ROJO
    color = AMBAR if dias <= 15 else TENUE
    verbo = "falta" if dias == 1 else "faltan"
    return f"{verbo} {_plural_dias(dias)}", color


def _campo(label: str, valor: str = "", ancho: int = 348, **extra) -> ft.TextField:
    return ft.TextField(
        label=label,
        value=valor,
        width=ancho,
        height=52,
        border_radius=12,
        border_color=BORDE,
        focused_border_color=OSCURO,
        bgcolor=SUPERFICIE,
        color=TEXTO,
        label_style=ft.TextStyle(color=TENUE, size=12),
        text_size=14,
        **extra,
    )


def _actualizar(control) -> None:
    """update() que no revienta si el control todavía no está en la página.

    En esta versión de Flet, leer `control.page` de un control sin montar
    LANZA RuntimeError en vez de devolver None, así que no sirve de guarda:
    hay que intentar el update y atrapar. Pasa de verdad — los diálogos
    llaman a _error()/_cargando() antes de que el control exista.
    """
    try:
        control.update()
    except (RuntimeError, AssertionError):
        pass


def _celda(texto: str, expand: int, **extra) -> ft.Text:
    # Los defaults van en un dict y no como argumentos con nombre: el
    # encabezado de la tabla llama a _celda(..., size=11, weight="bold"), y
    # con `size=13, **extra` eso reventaba con "got multiple values for
    # keyword argument 'size'".
    opciones = {
        "size": 13,
        "color": TEXTO,
        "max_lines": 1,
        "overflow": ft.TextOverflow.ELLIPSIS,
    }
    opciones.update(extra)
    return ft.Text(texto, expand=expand, **opciones)


# ----------------------------------------------------------------------
class DialogoEditar:
    """Editar nombre y las dos fechas de UN cliente.

    Campos de texto YYYY-MM-DD a propósito, sin DatePicker: son dos fechas que
    se tocan cada seis meses, no vale la pena el trámite.

    Mismo gotcha que los diálogos del panel de Taku Monky: AlertDialog(modal=
    True) no deja cancelar con tap-fuera ni con Escape en esta versión de Flet,
    así que la "X" explícita es la ÚNICA forma de salir — no quitarla. Y el
    guard `_ocupado` impide cerrarlo con un guardado a medio vuelo.
    """

    def __init__(self, page: ft.Page, fila_control: "FilaCliente"):
        self.page = page
        self.fila_control = fila_control
        self._ocupado = False
        datos = fila_control.datos or {}

        self.campo_nombre = _campo(
            "Nombre del negocio", datos.get("nombre") or "", autofocus=True
        )
        self.campo_inicio = _campo("Inicio (YYYY-MM-DD)", datos.get("fecha_inicio") or "")
        self.campo_fin = _campo("Fin (YYYY-MM-DD)", datos.get("fecha_fin") or "")

        self.texto_error = ft.Text("", size=12, color=ROJO)

        self._texto_boton = ft.Text("Guardar cambios", color="#ffffff", weight="bold", size=15)
        self.boton_guardar = ft.Container(
            content=self._texto_boton,
            alignment=ft.Alignment(0, 0),
            bgcolor=OSCURO,
            border_radius=12,
            width=348,
            padding=ft.padding.symmetric(vertical=15),
            ink=True,
            on_click=self._on_guardar,
        )
        self.boton_cerrar = ft.Container(
            content=ft.Icon(ft.Icons.CLOSE, size=16, color=TENUE),
            width=30,
            height=30,
            border_radius=15,
            ink=True,
            alignment=ft.Alignment(0, 0),
            on_click=lambda e: self._cerrar(),
            top=10,
            right=10,
            tooltip="Cerrar",
        )

        self.dialog = ft.AlertDialog(
            modal=True,
            bgcolor=SUPERFICIE,
            shape=ft.RoundedRectangleBorder(radius=18),
            content_padding=ft.padding.symmetric(horizontal=32, vertical=32),
            content=ft.Stack(
                controls=[
                    ft.Container(
                        width=348,
                        content=ft.Column(
                            # tight=True o el Column reclama todo el alto
                            # disponible y estira la tarjeta con él.
                            tight=True,
                            spacing=0,
                            controls=[
                                ft.Text("LICENCIA", size=11, weight="bold", color=TENUE),
                                ft.Text(
                                    fila_control.cliente["nombre"],
                                    size=22,
                                    weight="bold",
                                    color=OSCURO,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Container(height=20),
                                self.campo_nombre,
                                ft.Container(height=12),
                                self.campo_inicio,
                                ft.Container(height=12),
                                self.campo_fin,
                                ft.Container(height=8),
                                ft.Text(
                                    "Las fechas son de referencia: la licencia no se "
                                    "apaga sola. Déjalas vacías si no aplica.",
                                    size=11,
                                    color=TENUE,
                                ),
                                ft.Container(height=8),
                                self.texto_error,
                                ft.Container(height=12),
                                self.boton_guardar,
                            ],
                        ),
                    ),
                    self.boton_cerrar,
                ],
            ),
        )

    def abrir(self):
        self.page.show_dialog(self.dialog)

    def _cerrar(self):
        if self._ocupado:
            return
        self.page.pop_dialog()

    def _on_guardar(self, e):
        nombre = (self.campo_nombre.value or "").strip()
        inicio = (self.campo_inicio.value or "").strip()
        fin = (self.campo_fin.value or "").strip()

        if not nombre:
            self._error("El nombre no puede quedar vacío.")
            return
        for etiqueta, texto in (("inicio", inicio), ("fin", fin)):
            if texto and not _fecha_valida(texto):
                self._error(f"La fecha de {etiqueta} debe ir como YYYY-MM-DD (o vacía).")
                return

        self._error("")
        self.page.run_task(
            self._guardar,
            {
                "nombre": nombre,
                # Vacío se guarda como NULL, no como "": la columna es `date`.
                "fecha_inicio": inicio or None,
                "fecha_fin": fin or None,
            },
        )

    async def _guardar(self, datos: dict):
        self._cargando(True)
        error = await self.fila_control.guardar(datos)
        if error:
            self._error(error)
            self._cargando(False)
            return
        # Primero soltar el guard, si no _cerrar() se niega a cerrar.
        self._cargando(False)
        self._cerrar()

    def _error(self, mensaje: str):
        self.texto_error.value = mensaje
        _actualizar(self.texto_error)

    def _cargando(self, cargando: bool):
        self._ocupado = cargando
        self.boton_guardar.disabled = cargando
        self.boton_guardar.content = (
            ft.ProgressRing(width=18, height=18, stroke_width=2, color="#ffffff")
            if cargando
            else self._texto_boton
        )
        _actualizar(self.boton_guardar)


# ----------------------------------------------------------------------
class FilaCliente(ft.Container):
    """Un renglón de la tabla = un cliente = un proyecto de Supabase.

    Se construye en estado "Conectando..." y se llena sola cuando su propio
    cargar() termina. Todo lo que pueda fallar se atrapa AQUÍ dentro: esta
    fila puede quedar en rojo sin afectar a las demás.
    """

    def __init__(self, page: ft.Page, cliente: dict):
        super().__init__()
        self.page_ref = page
        self.cliente = cliente
        self.datos: dict | None = None
        self._dao: ConfiguracionNegocioDAO | None = None
        self._montada = False

        self.bgcolor = SUPERFICIE
        self.padding = ft.padding.symmetric(horizontal=18, vertical=12)
        self.border = ft.border.only(bottom=ft.BorderSide(1, BORDE))

        self.texto_negocio = ft.Text(
            cliente["nombre"],
            size=14,
            weight="bold",
            color=OSCURO,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        # El correo distingue dos renglones que apunten al mismo proyecto con
        # usuarios distintos (justo el caso con el que se prueba este panel).
        self.texto_correo = ft.Text(
            cliente["correo"],
            size=11,
            color=TENUE,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        self.celda_inicio = _celda("—", _W_CELDA)
        self.celda_fin = _celda("—", _W_CELDA)
        self.celda_restan = _celda("—", _W_CELDA)

        self.switch = ft.Switch(
            value=False,
            active_color=VERDE,
            disabled=True,
            on_change=self._on_switch,
        )
        self.texto_estado = ft.Text("—", size=12, weight="bold", color=TENUE)
        self.celda_estado = ft.Row(
            expand=_W_CELDA,
            spacing=2,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[self.switch, self.texto_estado],
        )

        self.boton_editar = ft.Container(
            content=ft.Icon(ft.Icons.EDIT_OUTLINED, size=16, color=TENUE),
            width=30,
            height=30,
            alignment=ft.Alignment(0, 0),
            border_radius=15,
            ink=True,
            visible=False,
            on_click=lambda e: DialogoEditar(self.page_ref, self).abrir(),
            tooltip="Editar nombre y fechas",
        )

        self.fila_datos = ft.Row(
            expand=_W_RESTO,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                self.celda_inicio,
                self.celda_fin,
                self.celda_restan,
                self.celda_estado,
                ft.Container(width=_W_ACCIONES, content=self.boton_editar),
            ],
        )
        self.zona_mensaje = ft.Row(
            expand=_W_RESTO,
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[],
        )
        self.zona = ft.Container(expand=_W_RESTO, content=self.zona_mensaje)

        self.texto_aviso = ft.Text("", size=11, color=ROJO, visible=False)

        self.content = ft.Column(
            tight=True,
            spacing=4,
            controls=[
                ft.Row(
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Column(
                            expand=_W_NEGOCIO,
                            tight=True,
                            spacing=0,
                            controls=[self.texto_negocio, self.texto_correo],
                        ),
                        self.zona,
                    ],
                ),
                self.texto_aviso,
            ],
        )
        self._pintar_cargando()

    # -- estados -------------------------------------------------------
    def did_mount(self):
        self._montada = True

    def will_unmount(self):
        self._montada = False

    def _refrescar(self):
        # Solo se puede update() si la fila ya está montada en la página, y
        # cuando corre __init__ todavía no lo está. La bandera es más barata
        # que la excepción, pero _actualizar() cubre la carrera de que
        # did_mount aún no haya llegado.
        if self._montada:
            _actualizar(self)

    def _pintar_cargando(self):
        self.zona_mensaje.controls = [
            ft.ProgressRing(width=16, height=16, stroke_width=2, color=OSCURO),
            ft.Text("Conectando...", size=12, color=TENUE),
        ]
        self.zona.content = self.zona_mensaje
        self.texto_aviso.visible = False
        self._refrescar()

    def _pintar_error(self, mensaje: str):
        self.zona_mensaje.controls = [
            ft.Icon(ft.Icons.ERROR_OUTLINE, size=15, color=ROJO),
            ft.Text(mensaje, size=12, color=ROJO, expand=True, max_lines=2),
        ]
        self.zona.content = self.zona_mensaje
        self._refrescar()

    def _pintar_datos(self):
        fila = self.datos or {}
        self.texto_negocio.value = fila.get("nombre") or self.cliente["nombre"]
        self.celda_inicio.value = fila.get("fecha_inicio") or "—"
        self.celda_fin.value = fila.get("fecha_fin") or "—"
        texto, color = _texto_restan(fila.get("fecha_fin"))
        self.celda_restan.value = texto
        self.celda_restan.color = color

        activo = bool(fila.get("activo"))
        self.switch.value = activo
        self.switch.disabled = False
        self.texto_estado.value = "Activa" if activo else "Apagada"
        self.texto_estado.color = VERDE if activo else ROJO
        self.boton_editar.visible = True

        self.zona.content = self.fila_datos
        self._refrescar()

    def _aviso(self, mensaje: str):
        self.texto_aviso.value = mensaje
        self.texto_aviso.visible = bool(mensaje)
        self._refrescar()

    # -- carga ---------------------------------------------------------
    async def cargar(self):
        """Login + lectura de su configuracion_negocio. No levanta nunca:
        cualquier error se pinta en esta misma fila."""
        self._pintar_cargando()
        try:
            supa = await asyncio.to_thread(conectar, self.cliente)
        except Exception as err:  # noqa: BLE001 — la fila no puede tumbar al panel
            print(f"[licencias] {self.cliente['nombre']}: no se pudo conectar: {err}")
            self._pintar_error(traducir_error(err, "conectar"))
            return

        self._dao = ConfiguracionNegocioDAO(supa)
        try:
            self.datos = await asyncio.to_thread(self._dao.obtener)
        except Exception as err:  # noqa: BLE001
            print(f"[licencias] {self.cliente['nombre']}: no se pudo leer: {err}")
            self._pintar_error(traducir_error(err, "leer"))
            return

        self._pintar_datos()

    async def guardar(self, datos: dict) -> str | None:
        """Escribe en ESE proyecto y repinta la fila.
        Devuelve None si salió bien, o el texto del error."""
        if self._dao is None or not self.datos:
            return "Esta fila no está conectada."
        try:
            self.datos = await asyncio.to_thread(
                self._dao.actualizar, datos, self.datos["id"]
            )
        except Exception as err:  # noqa: BLE001
            print(f"[licencias] {self.cliente['nombre']}: no se pudo guardar: {err}")
            return traducir_error(err, "guardar")
        self._aviso("")
        self._pintar_datos()
        return None

    def _on_switch(self, e):
        self.page_ref.run_task(self._cambiar_activo, bool(self.switch.value))

    async def _cambiar_activo(self, nuevo: bool):
        self.switch.disabled = True
        self._refrescar()
        error = await self.guardar({"activo": nuevo})
        if error:
            # Regresar el switch a como estaba: si RLS bloqueó el UPDATE en
            # silencio, dejarlo en verde sería mentir sobre el estado real.
            self.switch.value = not nuevo
            self.switch.disabled = False
            self.texto_estado.value = "Activa" if self.switch.value else "Apagada"
            self.texto_estado.color = VERDE if self.switch.value else ROJO
            self._aviso(error)


# ----------------------------------------------------------------------
class PanelLicencias(ft.Container):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page_ref = page
        self.expand = True
        self.bgcolor = FONDO
        self.padding = ft.padding.only(left=32, right=32, top=28, bottom=28)
        self._filas: list[FilaCliente] = []

        self.texto_titulo = ft.Text("Cargando clientes...", size=30, weight="bold", color=OSCURO)

        self.boton_recargar = ft.Container(
            content=ft.Row(
                spacing=8,
                controls=[
                    ft.Icon(ft.Icons.REFRESH, size=18, color="#ffffff"),
                    ft.Text("Recargar", color="#ffffff", weight="bold", size=14),
                ],
            ),
            bgcolor=OSCURO,
            padding=ft.padding.symmetric(horizontal=20, vertical=13),
            border_radius=12,
            ink=True,
            on_click=lambda e: self.page_ref.run_task(self._cargar_todo),
        )

        self.encabezado_tabla = ft.Container(
            bgcolor=ENCABEZADO,
            padding=ft.padding.symmetric(horizontal=18, vertical=11),
            border_radius=ft.border_radius.only(top_left=12, top_right=12),
            content=ft.Row(
                controls=[
                    _celda("NEGOCIO", _W_NEGOCIO, size=11, weight="bold", color=TENUE),
                    ft.Row(
                        expand=_W_RESTO,
                        controls=[
                            _celda("INICIO", _W_CELDA, size=11, weight="bold", color=TENUE),
                            _celda("FIN", _W_CELDA, size=11, weight="bold", color=TENUE),
                            _celda("RESTAN", _W_CELDA, size=11, weight="bold", color=TENUE),
                            _celda("ESTADO", _W_CELDA, size=11, weight="bold", color=TENUE),
                            ft.Container(width=_W_ACCIONES),
                        ],
                    ),
                ],
            ),
        )

        self.caja_avisos = ft.Container(visible=False)
        self.columna_filas = ft.Column(spacing=0, controls=[])
        self.tabla = ft.Column(
            spacing=0,
            controls=[self.encabezado_tabla, self.columna_filas],
        )

        self.content = ft.Column(
            expand=True,
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Column(
                            expand=True,
                            tight=True,
                            spacing=2,
                            controls=[
                                ft.Text("PANEL DE LICENCIAS", size=11, weight="bold", color=TENUE),
                                self.texto_titulo,
                            ],
                        ),
                        self.boton_recargar,
                    ],
                ),
                ft.Container(height=6),
                ft.Text(f"Clientes leídos de {RUTA_CLIENTES}", size=12, color=TENUE),
                ft.Container(height=18),
                self.caja_avisos,
                self.tabla,
            ],
        )

    def did_mount(self):
        self.page_ref.run_task(self._cargar_todo)

    # ------------------------------------------------------------------
    async def _cargar_todo(self):
        self._filas = []
        self.caja_avisos.visible = False
        self.tabla.visible = True
        self.texto_titulo.value = "Cargando clientes..."
        self.columna_filas.controls = [
            self._caja(
                ft.ProgressRing(width=20, height=20, stroke_width=2, color=OSCURO),
                "Leyendo clientes.json...",
            )
        ]
        self.update()

        try:
            clientes, avisos = await asyncio.to_thread(cargar_clientes)
        except ArchivoDeClientesInvalido as err:
            self.texto_titulo.value = "Sin clientes"
            self.tabla.visible = False
            self._mostrar_avisos([str(err)], ROJO, "#fef2f2")
            self.update()
            return

        if avisos:
            self._mostrar_avisos(avisos, AMBAR, "#fffbeb")

        if not clientes:
            self.texto_titulo.value = "Sin clientes"
            self.columna_filas.controls = [
                self._caja(
                    ft.Icon(ft.Icons.INBOX_OUTLINED, size=26, color=TENUE),
                    "No hay ningún cliente utilizable en clientes.json.",
                )
            ]
            self.update()
            return

        self.texto_titulo.value = (
            "1 cliente" if len(clientes) == 1 else f"{len(clientes)} clientes"
        )
        self._filas = [FilaCliente(self.page_ref, c) for c in clientes]
        self.columna_filas.controls = self._filas
        self.update()

        # EN PARALELO: cada fila hace su propio login + lectura al mismo tiempo
        # que las demás. return_exceptions por si acaso — cargar() ya atrapa
        # todo, esto es el cinturón además de los tirantes.
        await asyncio.gather(*(f.cargar() for f in self._filas), return_exceptions=True)

    def _mostrar_avisos(self, avisos: list[str], color: str, fondo: str):
        self.caja_avisos.visible = True
        self.caja_avisos.bgcolor = fondo
        self.caja_avisos.border = ft.border.all(1, color)
        self.caja_avisos.border_radius = 12
        self.caja_avisos.padding = ft.padding.symmetric(horizontal=14, vertical=12)
        self.caja_avisos.margin = ft.margin.only(bottom=18)
        self.caja_avisos.content = ft.Column(
            tight=True,
            spacing=6,
            controls=[
                ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                    controls=[
                        ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, size=16, color=color),
                        ft.Text(a, size=12, color=color, expand=True, selectable=True),
                    ],
                )
                for a in avisos
            ],
        )

    def _caja(self, icono, texto: str):
        return ft.Container(
            bgcolor=SUPERFICIE,
            padding=ft.padding.symmetric(vertical=44),
            alignment=ft.Alignment(0, 0),
            content=ft.Column(
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
                controls=[icono, ft.Text(texto, size=13, color=TENUE)],
            ),
        )


def main(page: ft.Page):
    page.title = "Panel de licencias"
    page.theme_mode = "light"
    page.padding = 0
    page.bgcolor = FONDO
    page.window.width = 1120
    page.window.height = 720
    page.add(PanelLicencias(page))


if __name__ == "__main__":
    ft.run(main)
