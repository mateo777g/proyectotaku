import flet as ft

from models import perfil
from views.perfil_ventana import abrir_perfil
from views.piezas import CURVA, ZOOM, anillo_brillo, sin_auto_update
from views.tema import C

# --- BARRA LATERAL ---
# Una sola para todo el panel (la guía de Fragmentless, A4.5): MainController la pone a la
# izquierda de cada vista con crear_barra_lateral(router, ruta_activa).
#
# El menú lleva UNA píldora con el estilo de los botones de atajo (cara de blanco translúcido y
# brillo en dos esquinas). Se queda bajo la sección activa; con el cursor encima de una opción se
# desliza hasta ella y se enciende como un atajo (zoom, cara más clara, texto en blanco y el relevo
# del texto), y al salir el cursor del menú vuelve apagada a la activa.

# Las opciones: texto, icono y ruta de MainController.cambiar_vista. Un texto suelto es un título
# de grupo. Iconos sin relleno (_OUTLINED), como en el panel de Fragmentless.
SECCIONES = [
    ("Inicio", ft.Icons.GRID_VIEW_OUTLINED, "home"),
    "GENERAL",
    ("Mi menú", ft.Icons.LIST_ALT_OUTLINED, "menu"),
    ("Mesas", ft.Icons.TABLE_RESTAURANT_OUTLINED, "mesas"),
    ("Agente IA", ft.Icons.SMART_TOY_OUTLINED, "agente_financiero"),
    ("Crear contenido", ft.Icons.AUTO_AWESOME_OUTLINED, "contenido"),
    ("Mi biblioteca", ft.Icons.PHOTO_LIBRARY_OUTLINED, "biblioteca"),
]
# Abajo: la ayuda por WhatsApp (antes la tarjeta dorada "¿Necesitas ayuda?"), Ajustes y
# "Cerrar sesión". La ayuda y cerrar sesión no son vistas, son acciones (ver al_pulsar).
AYUDA = "ayuda"
CERRAR = "cerrar_sesion"
SECCIONES_PIE = [
    "OTROS",
    ("Ayuda", ft.Icons.SUPPORT_AGENT_OUTLINED, AYUDA),
    ("Ajustes", ft.Icons.SETTINGS_OUTLINED, "ajustes"),
    ("Cerrar sesión", ft.Icons.LOGOUT, CERRAR),
]
# La línea de soporte del desarrollador (la de la tarjeta de ayuda de antes).
URL_AYUDA = "https://wa.me/5212723662604"
# Una insignia junto al texto de una opción: la pastilla de A4.13, sin color.
INSIGNIAS = {"agente_financiero": "IA"}

# El plan: lo enseñan el pie de la barra y la marca ("Plan Básico"). Escrito una sola vez para
# que no puedan quedar distintos (regla 9).
PLAN = "Básico"

ANCHO_BARRA = 330     # como la barra del panel viejo; en 250 se veía chica en pantalla grande
ANCHO = ANCHO_BARRA - 40   # la barra menos su margen de 20 por lado
ALTO = 44             # cada opción: padding 12 + icono 20 + padding 12
PASO = ALTO + 10      # una opción cada 54 px
# Un título de grupo: lo que ocupa entre la opción de arriba y la de abajo, además del PASO. La
# letra va a 8 de la opción de arriba y a 6 de la píldora de abajo; el primero de un menú va
# arriba del todo, a 6 de su primera opción.
TITULO_ALTO = 30
TITULO_ENCIMA = 8
TITULO_PRIMERO = 22
RADIO = ALTO // 2     # píldora: extremos en semicírculo


def crear_barra_lateral(router, activa):
    # Se lee aquí una vez: son dos menús y el primero lo apagaría antes de que lo viera el otro.
    encendida = getattr(router, "menu_encendido", False)
    router.menu_encendido = False
    return ft.Container(
        width=ANCHO_BARRA,
        bgcolor=C.barra,
        # Línea fina en el borde derecho. El borde cuenta como padding, por eso el margen derecho
        # de cada parte es 19: así el menú sigue midiendo ANCHO.
        border=ft.Border(right=ft.BorderSide(1, C.linea)),
        padding=ft.Padding(left=0, top=25, right=0, bottom=20),
        content=ft.Column([
            _con_margen(marca()),
            ft.Divider(height=30, color=C.tenue),
            # El menú de arriba ocupa lo que sobra y empuja el de abajo al fondo. Taku tiene más
            # opciones que Anxie: en una ventana baja (menos de ~770 px) el menú de arriba se
            # desplaza con la rueda en vez de montarse sobre el de abajo. El margen va DENTRO del
            # desplazamiento para que el zoom de la píldora (1.05) no se recorte a los lados.
            ft.Column([
                _con_margen(_crear_menu(router, SECCIONES, activa, encendida), arriba=5),
            ], expand=True, scroll=ft.ScrollMode.AUTO, spacing=0),
            _con_margen(_crear_menu(router, SECCIONES_PIE, activa, encendida)),
            ft.Divider(height=20, color=C.tenue),
            _con_margen(_pie_usuario(router)),
        ], spacing=10)
    )


def _con_margen(contenido, arriba=0):
    # El margen de la barra: 20 por lado (19 a la derecha, porque el borde de 1 cuenta como
    # padding), así lo de dentro sigue midiendo ANCHO.
    return ft.Container(padding=ft.Padding(left=20, top=arriba, right=19, bottom=0), content=contenido)


DIAMETRO_AVATAR = 32


def _pie_usuario(router):
    # El pie de la barra (como el "Mateo · Pro" de Claude): un círculo con la inicial y, al lado,
    # "Ary · Básico". Es un botón: con el cursor encima, una píldora del menú lo rodea y crece como
    # una opción; al pulsarlo se abre la ventana Perfil. Mide lo que una opción (ANCHO × ALTO) y el
    # círculo va a 6 del borde: su centro cae en la columna de los iconos del menú.
    radio = DIAMETRO_AVATAR // 2
    inicial = ft.Text(color=C.texto, size=14, font_family="LetraTitulo")
    avatar = ft.Container(
        width=DIAMETRO_AVATAR, height=DIAMETRO_AVATAR,
        content=ft.Stack([
            ft.Container(left=0, top=0, right=0, bottom=0, border_radius=radio, bgcolor=C.cara_encendida,
                         alignment=ft.Alignment.CENTER, content=inicial),
            anillo_brillo(ft.Alignment(-1, -1), radio, DIAMETRO_AVATAR),
            anillo_brillo(ft.Alignment(1, 1), radio, DIAMETRO_AVATAR),
        ], clip_behavior=ft.ClipBehavior.NONE)
    )
    # Un nombre largo se corta con "…" y el plan no se mueve de su sitio.
    nombre = ft.Text(color=C.texto, size=14, font_family="LetraTitulo",
                     max_lines=1, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS,
                     expand=1, expand_loose=True)
    fila = ft.Row([
        avatar,
        ft.Row([
            nombre,
            ft.Text("·", color=C.texto_suave, size=14, font_family="LetraTexto"),
            ft.Text(PLAN, color=C.texto_suave, size=14, font_family="LetraTexto"),
        ], spacing=6, expand=True),
    ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def pintar_nombre():
        llamarte = perfil.como_llamarte()
        nombre.value = llamarte
        inicial.value = llamarte[:1].upper()

    pintar_nombre()

    # La píldora de las opciones del menú, encendida, invisible hasta que llega el cursor.
    pildora = ft.Container(
        left=0, top=0, right=0, bottom=0, opacity=0, animate_opacity=CURVA,
        content=ft.Stack([
            anillo_brillo(ft.Alignment(-1, -1), RADIO, ALTO),
            anillo_brillo(ft.Alignment(1, 1), RADIO, ALTO),
            ft.Container(left=0, top=0, right=0, bottom=0, border_radius=RADIO, bgcolor=C.cara_encendida),
        ], clip_behavior=ft.ClipBehavior.NONE)
    )
    boton = ft.Container(
        width=ANCHO, height=ALTO, animate_scale=CURVA,
        content=ft.Stack([
            pildora,
            ft.Container(left=0, top=0, right=0, bottom=0, alignment=ft.Alignment.CENTER_LEFT,
                         padding=ft.Padding(left=6, top=0, right=16, bottom=0), content=fila),
        ], clip_behavior=ft.ClipBehavior.NONE)
    )

    def encender(dentro):
        pildora.opacity = 1 if dentro else 0
        boton.scale = ZOOM if dentro else 1
        boton.update()

    def al_cambiar_perfil():
        # Lo llama la ventana Perfil al guardar: el nombre nuevo, sin rehacer la vista.
        pintar_nombre()
        boton.update()

    boton.on_hover = sin_auto_update(lambda e: encender(e.data in (True, "true")))
    boton.on_click = sin_auto_update(lambda _: abrir_perfil(router))
    # Siempre el de la barra que se ve: cada vista hace la suya y la nueva pisa a la vieja.
    router.pintores_perfil = dict(getattr(router, "pintores_perfil", None) or {}, pie=al_cambiar_perfil)
    return boton


def marca(**kwargs):
    # El logo y la marca: arriba de la barra (una pieza, regla 9).
    return ft.Row([
        ft.CircleAvatar(radius=25, background_image_src="assets/fragmentless.png", bgcolor=ft.Colors.WHITE),
        ft.Column([
            ft.Text("FRAGMENTLESS", color=C.texto, size=18, font_family="LetraTitulo"),
            ft.Text(f"Plan {PLAN}", color=C.texto, size=12, font_family="LetraTitulo")
        ], spacing=0)
    ], **kwargs)


def _crear_menu(router, secciones, activa, encendida):
    # Un grupo de opciones con su píldora: el de arriba y el de abajo (OTROS). Si la vista activa
    # no es de este grupo, la píldora descansa invisible y solo aparece con el cursor encima.
    tops, titulos, y = [], [], 0
    for cosa in secciones:
        if isinstance(cosa, str):
            titulos.append(_crear_titulo(cosa, y + TITULO_ENCIMA if y else 0))
            y += TITULO_ALTO if y else TITULO_PRIMERO
        else:
            tops.append(y)
            y += PASO
    secciones = [cosa for cosa in secciones if not isinstance(cosa, str)]
    rutas = [ruta for _, _, ruta in secciones]
    indice_activo = rutas.index(activa) if activa in rutas else None
    # Si se llega aquí por un clic en el menú, el cursor sigue encima de la opción pulsada: la
    # barra nueva nace ya encendida ahí (si no, el zoom y el relevo se repetirían a cada clic).
    estado = {"indice": indice_activo if indice_activo is not None else 0,
              "encendida": encendida and indice_activo is not None}

    cara = ft.Container(
        left=0, top=0, right=0, bottom=0, border_radius=RADIO,
        animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT)
    )
    pildora = ft.Container(
        left=0, width=ANCHO, height=ALTO,
        animate_position=CURVA, animate_scale=CURVA, animate_opacity=CURVA,
        # Sin recorte: las máscaras de los anillos sobresalen 2 px de la caja a propósito.
        content=ft.Stack([
            anillo_brillo(ft.Alignment(-1, -1), RADIO, ALTO),
            anillo_brillo(ft.Alignment(1, 1), RADIO, ALTO),
            cara
        ], clip_behavior=ft.ClipBehavior.NONE)
    )
    opciones = [_crear_opcion(texto, icono, tops[i], INSIGNIAS.get(ruta))
                for i, (texto, icono, ruta) in enumerate(secciones)]

    def pintar():
        i, encendida = estado["indice"], estado["encendida"]
        pildora.opacity = 1 if encendida or indice_activo is not None else 0
        pildora.top = tops[i]
        pildora.scale = ZOOM if encendida else 1
        cara.bgcolor = C.cara_encendida if encendida else C.cara
        for k, (_, pintar_opcion) in enumerate(opciones):
            pintar_opcion(encendida and k == i)

    def mover(i, encendida):
        if (estado["indice"], estado["encendida"]) == (i, encendida):
            return
        if pildora.opacity == 0 and i != estado["indice"]:
            # Estaba invisible en otra opción: aparece donde está el cursor, sin deslizarse
            # desde allí. Primero salta sin animación (aún invisible) y luego se enciende.
            pildora.animate_position = None
            pildora.top = tops[i]
            pildora.update()
            pildora.animate_position = CURVA
        estado.update(indice=i, encendida=encendida)
        pintar()
        menu.update()

    def al_pasar(i):
        def manejador(e):
            # Solo al entrar: la vuelta a la activa la da el menú entero al salir (abajo).
            if e.data in (True, "true"):
                mover(i, True)
        return manejador

    def al_pulsar(ruta):
        if ruta == CERRAR:
            async def cerrar(_):
                ft.context.disable_auto_update()
                await router.cerrar_sesion()
            return cerrar
        if ruta == AYUDA:
            return sin_auto_update(lambda _: router.page.launch_url(URL_AYUDA))

        def manejador(_):
            router.menu_encendido = True
            router.cambiar_vista(ruta)
        return sin_auto_update(manejador)

    def al_salir_del_menu(e):
        # La vuelta va aquí y no en la salida de cada opción: entre opciones hay 10 px de
        # hueco, y al cruzarlo la píldora arrancaría hacia la activa y se daría la vuelta.
        if e.data not in (True, "true"):
            mover(indice_activo if indice_activo is not None else estado["indice"], False)

    # Todo sin auto-update: mover() hace menu.update() y cambiar_vista() el suyo.
    for i, ((opcion, _), (_, _, ruta)) in enumerate(zip(opciones, secciones)):
        opcion.on_hover = sin_auto_update(al_pasar(i))
        opcion.on_click = al_pulsar(ruta)

    pintar()
    menu = ft.Container(
        on_hover=sin_auto_update(al_salir_del_menu),
        # Alto fijo: un Stack con todo posicionado no sabe medirse dentro de una Column.
        # Sin recorte: se comería la holgura de los anillos y el zoom de la píldora.
        content=ft.Stack(
            titulos + [pildora] + [opcion for opcion, _ in opciones],
            width=ANCHO, height=tops[-1] + ALTO,
            clip_behavior=ft.ClipBehavior.NONE
        )
    )
    return menu


def _crear_titulo(texto, top):
    # El título de un grupo: LetraTitulo 11 en el gris de los subtítulos, con las letras algo
    # separadas, alineado con los iconos de las opciones (su padding de 12).
    return ft.Container(
        left=12, top=top,
        content=ft.Text(texto, color=C.texto_suave, size=11, font_family="LetraTitulo",
                        style=ft.TextStyle(letter_spacing=1.2)),
    )


def _crear_opcion(texto, icono, top, insignia=None):
    # Una opción del menú: solo icono y texto, sin fondo (el fondo es la píldora). La fila está
    # escrita dos veces para el relevo y va en blanco dentro de una capa al 54 % que sube al 100 %
    # al encenderse. Sin ink.
    # `insignia` ("IA"): una pastilla sin color (la cara de un botón) pegada a la derecha.
    def fila():
        return ft.Row([
            ft.Icon(icono, color=C.texto, size=20),
            ft.Text(texto, color=C.texto, size=14, font_family="LetraTexto")
        ], tight=True)

    sale = ft.Container(content=fila(), animate_offset=CURVA)
    entra = ft.Container(content=fila(), animate_offset=CURVA)
    rodillo = ft.Container(
        content=ft.Stack([sale, entra]),
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
        animate_opacity=CURVA
    )
    contenido = rodillo
    if insignia:
        contenido = ft.Row([
            ft.Container(content=rodillo, expand=True),
            ft.Container(
                bgcolor=C.cara, border_radius=9,
                padding=ft.Padding(left=8, top=3, right=8, bottom=3),
                content=ft.Text(insignia, color=C.texto_suave, size=10, font_family="LetraTexto"),
            ),
        ], spacing=8)
    opcion = ft.Container(
        left=0, top=top, width=ANCHO, height=ALTO, padding=12,
        alignment=ft.Alignment.CENTER_LEFT,
        content=contenido,
        animate_scale=CURVA
    )

    def pintar(encendida):
        opcion.scale = ZOOM if encendida else 1
        rodillo.opacity = 1 if encendida else C.reposo
        sale.offset = ft.Offset(0, -1 if encendida else 0)
        entra.offset = ft.Offset(0, 0 if encendida else 1)

    return opcion, pintar
