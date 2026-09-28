import traceback

import flet as ft

from models import perfil
from views.piezas import (aviso, boton_atajo, cabecera_tarjeta, campo, capa_ventana,
                          sin_auto_update, tarjeta_iphone)
from views.tema import C

# --- VENTANA "PERFIL" ---
# Se abre al pulsar el pie de la barra lateral (la guía de Fragmentless, A4.6): "Nombre completo"
# y "¿Cómo quieres que Fragmentless te llame?". Por ahora sin foto. Lo que se guarda está en
# models/perfil.py.
#
# No es de una sección, es de todo el panel: su capa va en page.overlay, encima de la ventana
# entera (la barra incluida), como la de Claude, y no dentro de una vista como las de Mi menú. Se
# crea una vez y se queda ahí; al cambiar de vista no se pierde.

ANCHO_TARJETA = 620
ANCHO_CAMPO = 260
MAXIMO = 20                 # lo que cabe en el saludo de Inicio sin salirse
ABAJO = 9                   # los avisos, en el hueco de debajo de la tarjeta (como en las ventanas de las vistas)


def abrir_perfil(router):
    page = router.page
    ventana = getattr(router, "ventana_perfil", None)
    if ventana is None:
        capa, abrir, cerrar = capa_ventana(page)
        ventana = router.ventana_perfil = {"capa": capa, "abrir": abrir, "cerrar": cerrar}
        # El velo cierra con el cerrar() de esta vez, que además le devuelve Escape a la vista.
        capa.on_click = sin_auto_update(lambda _: ventana["al_cerrar"]())
        page.overlay.append(capa)
        page._overlay.update()

    campo_nombre = campo(pista="Tu nombre y apellidos", valor=perfil.nombre_completo(), tamano=13,
                         expand=False)
    # Sin pista: el dueño no quiso un "Ej: …".
    campo_llamarte = campo(valor=perfil.elegido(), tamano=13, expand=False)
    for c in (campo_nombre, campo_llamarte):
        c.width = ANCHO_CAMPO

    def cerrar():
        # Escape vuelve a ser de la vista (las que cierran con él sus ventanitas).
        if page.on_keyboard_event == al_teclear:
            page.on_keyboard_event = anterior
        ventana["cerrar"]()

    def guardar(_=None):
        llamarte = campo_llamarte.value.strip()
        if len(llamarte) > MAXIMO:
            aviso(page, f"Cómo te llamo: máximo {MAXIMO} letras.", abajo=ABAJO)
            return
        try:
            perfil.guardar(campo_nombre.value, llamarte)
        except OSError:
            traceback.print_exc()
            aviso(page, "No se pudo guardar el perfil.", abajo=ABAJO)
            return
        cerrar()
        # El nombre nuevo, ya: en el pie de la barra que se ve y en el saludo de Inicio si está.
        for pintar in (getattr(router, "pintores_perfil", None) or {}).values():
            try:
                pintar()
            except RuntimeError:
                pass            # un pintor de una vista que ya no está en pantalla
        aviso(page, "Perfil guardado.")

    def al_teclear(e):
        ft.context.disable_auto_update()
        if e.key == "Escape":
            cerrar()

    # Enter en cualquiera de los dos campos guarda, como "Guardar cambios".
    campo_nombre.on_submit = sin_auto_update(guardar)
    campo_llamarte.on_submit = sin_auto_update(guardar)

    tarjeta = tarjeta_iphone(ft.Column([
        *cabecera_tarjeta("PERFIL", "Tus datos y cómo te llama Fragmentless en el panel."),
        _fila("Nombre completo", campo_nombre),
        ft.Divider(height=1, thickness=1, color=C.linea),
        _fila("¿Cómo quieres que Fragmentless te llame?", campo_llamarte),
        ft.Container(height=20),
        ft.Row([boton_atajo(ft.Icons.CHECK, "Guardar cambios", guardar),
                boton_atajo(ft.Icons.CLOSE, "Cancelar", lambda _: cerrar())], spacing=25),
    ], spacing=10, tight=True), expand=None)
    tarjeta.width = ANCHO_TARJETA

    # Escape cierra, mientras está abierta. Se cambia el manejador sin page.update(): con uno ya
    # puesto no hace falta, y en las demás vistas se comprobó que llega igual; un
    # page.update() compararía la página entera (en Mi biblioteca llena, más de 1 s).
    anterior = page.on_keyboard_event
    page.on_keyboard_event = al_teclear
    ventana["al_cerrar"] = cerrar
    ventana["abrir"](tarjeta)


def _fila(texto, control):
    # Una fila como las de Claude: la pregunta a la izquierda (Medium 14, blanco) y el campo a la
    # derecha, con aire arriba y abajo.
    return ft.Container(
        padding=ft.Padding(left=0, top=6, right=0, bottom=6),
        content=ft.Row([
            ft.Text(texto, color=C.texto, size=14, font_family="LetraTexto", expand=True),
            control,
        ], spacing=25, vertical_alignment=ft.CrossAxisAlignment.CENTER),
    )
