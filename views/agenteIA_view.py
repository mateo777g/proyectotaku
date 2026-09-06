import asyncio
import math
import traceback

import flet as ft

from models.ia_controller import IAController

# La conversación y la caja de texto miden lo mismo a propósito: así las
# burbujas quedan alineadas con los bordes de la caja en vez de flotar a su
# aire. 720 es el ancho que la caja ya tenía desde la Fase 6, o sea que la
# conversación se ajustó a ella y no al revés.
ANCHO_CHAT = 720

# Hueco que se le deja al lado contrario de cada burbuja: es lo que impide
# que un mensaje largo cruce la conversación de lado a lado. El del dueño se
# recorta más porque sus preguntas son cortas y así se lee claro quién habla.
HUECO_USUARIO = 170
HUECO_IA = 70

# Renglones que muestra la caja de texto antes de necesitar el botón de
# desplegar, y los que muestra ya desplegada.
LINEAS_COLAPSADA = 4
LINEAS_EXPANDIDA = 14

# Lo que miden los dos botones que viven dentro de la píldora, a la derecha
# del campo. Están aquí arriba y no sueltos en el código porque
# _lineas_estimadas() los tiene que restar del ancho para saber cuántos
# caracteres caben por renglón: si un botón cambia de tamaño y este número
# no, el botón de desplegar empieza a aparecer tarde o temprano de más.
ANCHO_BOTON_EXPANDIR = 30
ANCHO_BOTON_ENVIAR = 34
HUECO_BOTONES = 4

# El logo animado que se ve mientras la IA piensa. Es UN archivo WebP
# animado (36 cuadros, 70 ms cada uno, ~2.5 s por vuelta, con transparencia
# real), no los 36 SVG sueltos, y ese cambio arregló un fallo de verdad.
#
# ⚠️ NO lo regreses a "un SVG por cuadro con un temporizador de python".
# Así estaba, y en la máquina del desarrollador la animación se veía
# CONGELADA. Medido en un video suyo de la app real: el logo estuvo 3.87 s
# en pantalla y solo cambió de dibujo 3 veces —con un hueco de 1.70 s— donde
# tocaban ~55. La causa no es el diseño ni el tamaño: con un cuadro por
# archivo, python tiene que empujar 14 actualizaciones por segundo al
# cliente, y eso es lo primero que se muere cuando la máquina está ocupada,
# que es SIEMPRE en esta pantalla — mientras el logo gira, el mismo proceso
# está leyendo 4 tablas de Supabase, armando el prompt y esperando a OpenAI.
# Reproducido y medido: en reposo repintaba a 12.6 cuadros/s, con la CPU
# ocupada bajaba a 7.4, y en la máquina del desarrollador (más cargada, con
# la ventana maximizada y grabando video) a ~1.
#
# Con el WebP animado el cliente reproduce la animación SOLO y python no
# manda un solo cuadro: medido igual, 13.6 cuadros/s en reposo y 13.2 con la
# CPU al tope, o sea que ya no le afecta. De paso desaparecieron el
# threading.Timer, el .start()/.stop() y la trampa de autoplay.
#
# El archivo se generó desde los 36 SVG de assets/svg/ y esos se quedan como
# la FUENTE: si algún día cambia la secuencia, hay que volver a generarlo
# (ver el bloque de la Fase 6 en CLAUDE.md, que trae la receta exacta).
RUTA_LOGO_PENSANDO = "assets/logo-pensando.webp"

# Lado del logo y tamaño del "Pensando..." de al lado. Fueron subiendo el
# 2026-09-06: 28/13 al montarlo, 36/14 porque a 28 no se alcanzaba a apreciar
# que se movía —que es justo para lo que existe— y 42/14 al llegar la
# secuencia nueva de 36 cuadros. Los dos números viven aquí para que se
# puedan reajustar juntos: si uno crece y el otro no, la fila se desbalancea.
TAMANO_LOGO_PENSANDO = 42
TAMANO_TEXTO_PENSANDO = 14


def _icono(nombre, tamano: int, color: str) -> ft.Icon:
    """Un ft.Icon nuevo, para ASIGNARLO a .content del botón que lo usa.

    ⚠️ No cambies un icono ya montado con `mi_icono.name = ft.Icons.OTRO`:
    en esta versión de flet esa mutación NO se propaga al cliente — el
    icono se queda dibujado como estaba, para siempre y sin ningún error.
    Se comprobó con dos iconos lado a lado en la ventana real: al que se
    le mutó `.name` no se movió, y el que se reemplazó entero sí cambió.
    (Las propiedades del Container que lo envuelve —bgcolor, border_radius—
    sí se propagan, lo que hace el fallo todavía más confuso: medio botón
    cambia y el otro medio no.) Por eso los dos botones de la caja de
    texto reemplazan su `.content` en vez de mutar el icono; el de
    desplegar arrastraba justo ese bug y nunca llegaba a mostrar
    UNFOLD_LESS al expandirse.
    """
    return ft.Icon(nombre, size=tamano, color=color)


# Tipografía de las respuestas del agente (2026-09-06). Georgia es la serif
# que el proyecto YA usa en los títulos, así que no entra ninguna fuente
# nueva; el desarrollador la eligió comparando las tres opciones renderizadas
# en la ventana real, con la de Claude como referencia. 16 con interlineado
# 1.55 es lo que hace que un párrafo largo se lea descansado en vez de
# apretado — que era el punto.
FUENTE_RESPUESTA = "Georgia"
TAMANO_RESPUESTA = 16
INTERLINEADO_RESPUESTA = 1.55


def _estilo_markdown() -> ft.MarkdownStyleSheet:
    """Estilos con los que se pinta el markdown de las respuestas (ver
    _burbuja_ia). Todo sale de la paleta del proyecto, nada nuevo: cuerpo
    #1c1610, encabezados en el café de los rótulos (#806f61), y las cajas de
    tabla/cita/código en #f3ead4 — el mismo tono de superficie que #eee5cf le
    da a los encabezados de tabla en menu_view.py, un punto más claro para
    que se despegue sin gritar del fondo sobre el que caen, que desde que la
    respuesta perdió su burbuja es el de la vista (#fbf5e9).

    DOS BLOQUES SE QUEDAN FUERA DE GEORGIA, a propósito:

    - El código, que ya era Consolas desde siempre — una serif proporcional
      no sirve para eso.
    - Las TABLAS. Georgia dibuja los números en estilo antiguo (el 4 y el 7
      de "$4,147" bajan de la línea), que se ve elegante en un párrafo pero
      deja una columna de dinero visiblemente despareja, y una tabla existe
      justo para escanear cifras de arriba abajo. Se quedan en la sans por
      omisión, con números normales. No es una inconsistencia suelta: la
      tabla ya es un bloque aparte con su propio fondo #f3ead4, igual que el
      código, así que el cambio de fuente se lee como intencional.

    Devuelve una instancia nueva en cada llamada, en vez de ser una
    constante compartida por todas las burbujas: cuesta nada y evita
    preguntarse si flet puede reutilizar el mismo objeto en varios
    controles a la vez.
    """

    def prosa(**extra) -> ft.TextStyle:
        """Un estilo de párrafo: Georgia, 16, aireado."""
        extra.setdefault("size", TAMANO_RESPUESTA)
        extra.setdefault("color", "#1c1610")
        return ft.TextStyle(
            font_family=FUENTE_RESPUESTA,
            height=INTERLINEADO_RESPUESTA,
            **extra,
        )

    def titulo(tam: int, color: str) -> ft.TextStyle:
        """Un encabezado: Georgia también, pero más junto — el interlineado
        del cuerpo aquí solo abriría huecos."""
        return ft.TextStyle(
            font_family=FUENTE_RESPUESTA,
            size=tam,
            weight=ft.FontWeight.BOLD,
            color=color,
            height=1.3,
        )

    return ft.MarkdownStyleSheet(
        p_text_style=prosa(),
        strong_text_style=prosa(weight=ft.FontWeight.BOLD, color="#18120d"),
        em_text_style=prosa(italic=True),
        h1_text_style=titulo(21, "#18120d"),
        h2_text_style=titulo(19, "#18120d"),
        h3_text_style=titulo(17, "#806f61"),
        h4_text_style=titulo(16, "#806f61"),
        list_bullet_text_style=prosa(color="#8a7e72"),
        blockquote_text_style=prosa(size=15, color="#5e5449"),
        blockquote_decoration=ft.BoxDecoration(bgcolor="#f3ead4", border_radius=8),
        blockquote_padding=ft.padding.symmetric(horizontal=14, vertical=10),
        code_text_style=ft.TextStyle(size=14, font_family="Consolas", color="#bf571d"),
        codeblock_decoration=ft.BoxDecoration(bgcolor="#f3ead4", border_radius=8),
        codeblock_padding=ft.padding.symmetric(horizontal=12, vertical=10),
        # Sin font_family: la sans por omisión, por los números (ver arriba).
        table_head_text_style=ft.TextStyle(
            size=14, weight=ft.FontWeight.BOLD, color="#18120d"
        ),
        table_body_text_style=ft.TextStyle(size=14, color="#1c1610"),
        table_cells_padding=ft.padding.symmetric(horizontal=12, vertical=8),
        table_cells_decoration=ft.BoxDecoration(bgcolor="#f3ead4"),
        # Sube de 10 a 12 con el cuerpo más aireado: con párrafos de 16 y
        # interlineado 1.55, 10 los dejaba pegados entre si.
        block_spacing=12,
        list_indent=20,
    )


class AgenteIAView(ft.Container):
    """Pantalla del agente de IA.

    Tiene dos estados, igual que cualquier chat de IA grande, y cambia del
    primero al segundo una sola vez, con el primer mensaje:

    - BIENVENIDA: el saludo grande y la caja de texto, centrados en la
      pantalla, sin nada más.
    - CONVERSACIÓN: el saludo desaparece, los mensajes ocupan la pantalla de
      arriba hacia abajo con su propio scroll, y la caja de texto se ancla
      abajo.

    Antes las dos cosas vivían en la misma columna centrada, así que cada
    mensaje nuevo empujaba la caja hacia abajo y se amontonaban unos encima
    de otros. Ver _montar_bienvenida()/_montar_chat().
    """

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
        self._modo_chat = False
        self._entrada_expandida = False
        # Si la caja tiene el cursor dentro. Solo la usa
        # _aplicar_realce_caja(); en BIENVENIDA da igual lo que valga.
        self._entrada_enfocada = False
        # Numera las preguntas para poder desplazarse hasta la última con
        # scroll_to(scroll_key=...) — ver _ir_a().
        self._contador_preguntas = 0

        # --------------------------------------------------------------
        # Conversación
        # --------------------------------------------------------------
        self.lista_mensajes = ft.Column(
            spacing=18,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            # auto_scroll a propósito NO: dejaría la vista al final de la
            # respuesta, y en una respuesta larga eso significa aterrizar en
            # el último renglón y tener que subir a leer. En vez de eso se
            # usa scroll_to() con la clave de la pregunta para dejarla hasta
            # arriba (igual que ChatGPT/Claude), y flet exige que auto_scroll
            # esté apagado para que scroll_to funcione.
            auto_scroll=False,
        )

        self.zona_conversacion = ft.Container(
            content=self.lista_mensajes,
            width=ANCHO_CHAT,
            expand=True,
            padding=ft.padding.only(top=4, bottom=12),
        )

        # --------------------------------------------------------------
        # Caja de texto
        # --------------------------------------------------------------
        self.entrada = ft.TextField(
            hint_text="Escribe una pregunta sobre tu negocio...",
            expand=True,
            # multiline + shift_enter = el comportamiento de chat: Enter
            # manda la pregunta y Shift+Enter hace salto de línea. La caja
            # crece sola hasta LINEAS_COLAPSADA renglones.
            multiline=True,
            min_lines=1,
            max_lines=LINEAS_COLAPSADA,
            shift_enter=True,
            border=ft.InputBorder.NONE,
            # ⚠️ El campo NO pinta fondo: lo pinta caja_entrada y este va
            # transparente encima. No le pongas bgcolor "para que combine" —
            # ese es justo el bug que esto arregla. Un TextField con relleno
            # se dibuja ENCIMA del borde del Container que lo envuelve, y como
            # caja_entrada no tiene padding a la izquierda, se comía el tramo
            # central del borde izquierdo: la píldora salía con las curvas de
            # arriba y de abajo pero con un hueco en medio. Se ve a simple
            # vista al ampliar la esquina, y se confirmó comparando tres
            # variantes lado a lado (con relleno, con padding izquierdo, y
            # sin relleno): solo esta cierra el contorno.
            #
            # De paso resuelve lo que antes se parchaba con focused_bgcolor/
            # hover_color: Material oscurece el RELLENO del campo al enfocarlo
            # o al pasarle el mouse (medido: #f8f1de -> #eee8d5), y como los
            # botones le quitan 72 px a la derecha, esa franja se quedaba del
            # color original y la píldora se veía partida en dos tonos. Sin
            # relleno no hay nada que oscurecer, así que el problema no existe
            # y esas dos propiedades ya no hacen falta.
            filled=False,
            color="#1c1610",
            hint_style=ft.TextStyle(color="#8a7e72", size=15),
            text_size=15,
            content_padding=ft.padding.symmetric(horizontal=24, vertical=20),
            on_submit=self._enviar_mensaje,
            on_change=self._on_cambio_entrada,
            # Solo mueven el borde y la sombra de la caja en CONVERSACIÓN
            # — ver _aplicar_realce_caja(). En BIENVENIDA no cambian nada.
            on_focus=self._on_foco_entrada,
            on_blur=self._on_foco_entrada,
        )

        # Botón de desplegar: solo aparece cuando el texto del dueño ya no
        # cabe en la caja. Mismo formato de botón-icono que menu_view.py
        # (30x30, radio 15, ink) para que no se sienta de otra app.
        self.boton_expandir = ft.Container(
            content=_icono(ft.Icons.UNFOLD_MORE, 16, "#756b5e"),
            width=ANCHO_BOTON_EXPANDIR,
            height=ANCHO_BOTON_EXPANDIR,
            alignment=ft.Alignment(0, 0),
            border_radius=ANCHO_BOTON_EXPANDIR / 2,
            ink=True,
            visible=False,
            tooltip="Ver todo el mensaje",
            on_click=self._alternar_expansion,
        )

        # Botón de enviar: la caja vacía no muestra NADA a la derecha, y en
        # cuanto el dueño escribe algo aparece. Se ve distinto según el
        # estado de la pantalla — ver _estilizar_boton_enviar() para el
        # porqué de los dos aspectos.
        self.boton_enviar = ft.Container(
            alignment=ft.Alignment(0, 0),
            ink=True,
            visible=False,
            tooltip="Enviar (Enter)",
            on_click=self._enviar_mensaje,
        )
        self._estilizar_boton_enviar()

        # Misma superficie que la burbuja del usuario (#f8f1de); la de la IA
        # ya no tiene. El borde y la sombra NO
        # se declaran aqui a proposito: los pone _aplicar_realce_caja(), que
        # decide segun el estado de la pantalla y el foco.
        self.caja_entrada = ft.Container(
            width=ANCHO_CHAT,
            bgcolor="#f8f1de",
            border_radius=35,
            padding=ft.padding.only(right=12),
            content=ft.Row(
                controls=[self.entrada, self.boton_expandir, self.boton_enviar],
                spacing=HUECO_BOTONES,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )
        self._aplicar_realce_caja()

        # --------------------------------------------------------------
        # Saludo (solo en el estado de bienvenida)
        # --------------------------------------------------------------
        self.bloque_saludo = ft.Column(
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
            tight=True,
            spacing=0,
        )

        self.raiz = ft.Column(
            expand=True,
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self._montar_bienvenida()
        self.content = self.raiz

    # ------------------------------------------------------------------
    # Los dos estados de la pantalla
    # ------------------------------------------------------------------
    def _montar_bienvenida(self):
        """Saludo + caja, centrados. Los dos espaciadores que sobran arriba
        y abajo se reparten el hueco por igual, que es lo que deja el bloque
        justo a la mitad de la pantalla."""
        self.raiz.controls = [
            ft.Container(expand=True),
            self.bloque_saludo,
            ft.Container(height=34),
            self.caja_entrada,
            ft.Container(expand=True),
        ]

    def _montar_chat(self):
        """Conversación arriba (con su scroll) y caja anclada abajo. Se
        llama una sola vez, desde _enviar_mensaje, al mandar el primer
        mensaje: de ahí en adelante la pantalla ya no cambia de forma."""
        self._modo_chat = True
        self._estilizar_boton_enviar()
        # En chat la sombra pasa a depender del foco, y al mandar el primer
        # mensaje la caja se queda enfocada — o sea que aqui normalmente
        # sigue encendida; lo que cambia es que ahora se apagara al salir.
        self._aplicar_realce_caja()
        self.raiz.controls = [
            self.zona_conversacion,
            ft.Container(height=14),
            self.caja_entrada,
        ]

    # ------------------------------------------------------------------
    # Piezas de la conversación
    # ------------------------------------------------------------------
    def _fila(self, contenido: ft.Control, derecha: bool) -> ft.Container:
        """Coloca un mensaje de un lado o del otro de la conversación. El
        padding del lado contrario es el tope de ancho de la burbuja: sin él
        una respuesta larga se estiraría los 720 px completos y se perdería
        la lectura de quién dijo qué."""
        return ft.Container(
            content=contenido,
            alignment=ft.Alignment(1, 0) if derecha else ft.Alignment(-1, 0),
            padding=(
                ft.padding.only(left=HUECO_USUARIO)
                if derecha
                else ft.padding.only(right=HUECO_IA)
            ),
        )

    def _burbuja_usuario(self, texto: str) -> ft.Container:
        # La UNICA burbuja que queda en la pantalla: la de la IA se quito
        # para que la respuesta caiga directa sobre el fondo (ver
        # _burbuja_ia). Sus colores son los mismos de la caja de texto
        # (#f8f1de + borde #eadfca). Era dorada (#f4ca83, relleno y sin
        # borde) y el dueño la cambio a proposito: quiso que las piezas de
        # la pantalla se vieran igual de simples. Lo que distingue al
        # usuario de la IA es la alineacion (derecha vs izquierda), el ancho
        # maximo (HUECO_USUARIO vs HUECO_IA) y, desde que la IA perdio la
        # suya, tener burbuja o no tenerla.
        return ft.Container(
            content=ft.Text(texto, size=14, color="#1c1610"),
            bgcolor="#f8f1de",
            border=ft.border.all(1, "#eadfca"),
            padding=ft.padding.symmetric(horizontal=18, vertical=10),
            border_radius=20,
        )

    def _burbuja_ia(self, texto: str) -> ft.Container:
        # SIN burbuja, a propósito: la respuesta se pinta directa sobre el
        # fondo de la vista, como en Claude/ChatGPT. La del usuario sí
        # conserva la suya (#f8f1de + borde #eadfca), y esa diferencia es
        # ahora una tercera señal de quién habla, junto al lado y al ancho
        # máximo (ver _burbuja_usuario).
        # No se pinta bgcolor="#fbf5e9" a mano: un Container sin bgcolor ya
        # deja ver el fondo de la vista, y así sigue siendo correcto si ese
        # fondo cambia algún día. border_radius también se fue: sin
        # superficie ni borde no redondeaba nada.
        # selectable=True porque las respuestas suelen traer cifras/precios
        # que el dueño va a querer copiar.
        #
        # El texto va en ft.Markdown y no en ft.Text porque gpt-4o NO
        # contesta en texto pelón: contesta en markdown (**negritas**,
        # viñetas, ### encabezados, tablas con pipes). Con ft.Text esos
        # símbolos se pintaban crudos. Nada de esto cambia lo que responde
        # el modelo ni el prompt de models/ia_controller.py — es solo cómo
        # se pinta lo que ya llegaba.
        return ft.Container(
            content=ft.Markdown(
                texto,
                selectable=True,
                # GITHUB_FLAVORED es lo que habilita las tablas (y los
                # ~~tachados~~); con el set por defecto una tabla se queda
                # como un montón de pipes.
                extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED,
                # OBLIGATORIO, no es un adorno: en markdown un solo salto de
                # línea NO parte el renglón, así que una respuesta escrita
                # como "Mesa 1 — $2,150\nMesa 2 — $1,480" (sin viñetas, que
                # es como a veces contesta el modelo) se pegaría todo en un
                # párrafo corrido. Con esto en True cada salto se respeta,
                # igual que se veía con ft.Text.
                soft_line_break=True,
                md_style_sheet=_estilo_markdown(),
            ),
            # Sin bgcolor, sin border y sin border_radius: la burbuja de la
            # IA desapareció (ver el comentario de arriba).
            #
            # El padding horizontal también se quita (era 18). Sin una
            # superficie que lo justifique ese hueco solo dejaba el texto de
            # la IA sangrado 18 px respecto al borde izquierdo de la
            # conversación y respecto al "Pensando..." que aparece justo
            # antes en ese mismo sitio, que no lleva padding propio.
            # El vertical se queda en 12 a propósito: sumado al spacing=18 de
            # lista_mensajes da exactamente el mismo aire entre mensajes que
            # había con burbuja, o sea que quitarla no movió nada de sitio.
            padding=ft.padding.symmetric(horizontal=0, vertical=12),
        )

    def _burbuja_pensando(self) -> ft.Row:
        """La fila de "Pensando..." con el logo animado al lado.

        Es el ÚNICO indicador de carga de la app que no es un ProgressRing:
        los otros siete (menú, mesas, home, login y los dos diálogos) siguen
        con el aro dorado.

        El logo es un WebP animado que el cliente reproduce solo — python no
        manda un cuadro ni programa nada, y por eso esta función devuelve la
        fila y ya, sin referencias que arrancar o detener. Ver
        RUTA_LOGO_PENSANDO arriba para por qué dejó de ser un temporizador.

        Sin bgcolor ni contenedor de color detrás: el WebP lleva
        transparencia real, así que el fondo crema (#fbf5e9) se ve a través.
        """
        # spacing=8 y la alineación vertical se quedan como estaban desde el
        # ProgressRing (Row centra en vertical por omisión), así el texto
        # sigue a la misma altura aunque el logo mida 42 y no 16.
        return ft.Row(
            controls=[
                ft.Image(
                    src=RUTA_LOGO_PENSANDO,
                    width=TAMANO_LOGO_PENSANDO,
                    height=TAMANO_LOGO_PENSANDO,
                    fit=ft.BoxFit.CONTAIN,
                ),
                ft.Text(
                    "Pensando...",
                    size=TAMANO_TEXTO_PENSANDO,
                    color="#8a7e72",
                ),
            ],
            spacing=8,
            tight=True,
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
                    ft.Text(mensaje, size=13, color="#a33c39", expand=True),
                ],
                spacing=8,
            ),
        )

    # ------------------------------------------------------------------
    # Caja de texto: enviar, crecer, desplegar, plegar
    # ------------------------------------------------------------------
    def _on_foco_entrada(self, e):
        """Realza y apaga la caja al entrar y salir de ella.

        Es el mismo manejador para on_focus y on_blur: e.name dice cuál de
        los dos llegó, así que no hacen falta dos funciones casi idénticas.
        """
        self._entrada_enfocada = e.name == "focus"
        self._aplicar_realce_caja()
        self._refrescar()

    def _aplicar_realce_caja(self):
        """Decide cómo se ve la caja de texto: sombra y color del borde. No
        repinta — quien llama decide cuándo hacerlo.

        Las dos piezas NO siguen la misma regla, y esa asimetría es el punto
        entero de este método:

        - El BORDE responde al foco en los dos estados por igual: #eadfca en
          reposo (el mismo de las burbujas) y #d8c3a4 con el cursor dentro
          —el mismo tono oscurecido, no uno nuevo—, lo justo para notarse sin
          volverse un recuadro marcado. Nunca desaparece, solo cambia de
          intensidad.
        - La SOMBRA no: en BIENVENIDA está siempre encendida, porque ahí la
          caja es lo único que hay en la pantalla junto al saludo y la sombra
          es lo que la sostiene. En CONVERSACIÓN se apaga en reposo, para que
          la caja no compita con la respuesta que el dueño está leyendo, y se
          enciende al enfocar.

        El disparador es el FOCO, no el contenido: da igual si hay texto
        escrito o si la caja está vacía. Salió de mirar cómo se comportan los
        chats de las empresas grandes.

        Mientras la IA piensa la caja se ve plana, y es correcto: deshabilitar
        el campo dispara on_blur de verdad (medido), así que se apaga sola
        mientras no se puede escribir y se vuelve a encender al devolver el
        foco — ver el finally de _responder.

        Los números de la sombra (blur 10 / sin spread / 7% de negro / 2px de
        caída) vienen de que la primera versión —blur 24, spread 1, 30% de
        negro, offset (0,7)— se leía como una nube oscura. El dueño la mandó
        quitar, vio la caja completamente plana y pidió regresarla "pero no
        tan exagerada" y SIN quitarle el borde. Ese es el límite si se vuelve
        a tocar: se tiene que notar solo cuando la buscas.
        """
        # El BORDE responde al foco en los dos estados por igual.
        self.caja_entrada.border = ft.border.all(
            1, "#d8c3a4" if self._entrada_enfocada else "#eadfca"
        )
        # La SOMBRA no: en bienvenida está siempre, en chat solo con el foco.
        if self._modo_chat and not self._entrada_enfocada:
            self.caja_entrada.shadow = None
            return
        self.caja_entrada.shadow = ft.BoxShadow(
            blur_radius=10,
            spread_radius=0,
            color=ft.Colors.with_opacity(0.07, ft.Colors.BLACK),
            offset=ft.Offset(0, 2),
        )

    def _estilizar_boton_enviar(self):
        """Le da al botón de enviar el aspecto que le toca según el estado
        de la pantalla. No repinta — quien llama decide cuándo hacerlo.

        En BIENVENIDA es un cuadro naranja relleno: la pantalla está vacía,
        no hay ninguna otra cosa que mirar, y el botón es la invitación a
        mandar la primera pregunta. En CONVERSACIÓN se apaga al formato
        discreto de al lado —sin fondo, redondo, el mismo gris #756b5e del
        botón de desplegar— porque ahí ya compite con las burbujas y el
        dueño ya aprendió que Enter manda: un cuadro naranja gritando en
        cada respuesta cansa. El tamaño (34) no cambia entre los dos, para
        que la píldora no se encoja al mandar el primer mensaje.

        El naranja es #bf571d, el mismo del "¿En qué puedo ayudarte hoy?"
        que tiene justo encima, no un tono nuevo.
        """
        self.boton_enviar.width = ANCHO_BOTON_ENVIAR
        self.boton_enviar.height = ANCHO_BOTON_ENVIAR
        if self._modo_chat:
            self.boton_enviar.border_radius = ANCHO_BOTON_ENVIAR / 2
            self.boton_enviar.bgcolor = None
            self.boton_enviar.content = _icono(ft.Icons.KEYBOARD_RETURN, 17, "#756b5e")
        else:
            self.boton_enviar.border_radius = 12
            self.boton_enviar.bgcolor = "#bf571d"
            self.boton_enviar.content = _icono(ft.Icons.ARROW_UPWARD, 18, "#fbf5e9")

    def _lineas_estimadas(self, texto: str) -> int:
        """Cuántos renglones ocupa el texto dentro de la caja.

        Es una estimación: flet no expone la altura real que terminó
        midiendo el TextField, así que se aproxima el ancho medio de un
        carácter y se cuenta cada salto de línea aparte. Solo decide si
        aparece el botón de desplegar, o sea que fallar por un renglón no
        rompe nada.

        Los 7.9 px por carácter no son un número al aire: se midieron
        tecleando un texto real en la caja y contando dónde partía los
        renglones con text_size=15. Ese ancho por carácter es del tipo de
        letra, no de la caja, así que sigue valiendo aunque el campo se
        angoste; lo que cambia es cuántos caben (~74 por renglón desde que
        entró el botón de enviar, ~79 antes). Si se cambia ANCHO_CHAT o
        text_size, hay que volver a medir.
        """
        # Ancho real del campo: la píldora menos su padding derecho, menos
        # los dos botones con sus huecos, menos el padding horizontal del
        # propio TextField. Se cuentan los dos botones aunque el de
        # desplegar todavía no se vea, porque para cuando el texto llega a
        # desbordarse los dos están ahí.
        ancho_util = (
            ANCHO_CHAT
            - 12
            - (ANCHO_BOTON_EXPANDIR + ANCHO_BOTON_ENVIAR + HUECO_BOTONES * 2)
            - 24 * 2
        )
        por_renglon = max(20, int(ancho_util / 7.9))
        renglones = 0
        for parrafo in texto.split("\n"):
            renglones += max(1, math.ceil(len(parrafo) / por_renglon))
        return renglones

    def _plegar_entrada(self):
        """Regresa la caja a su tamaño normal. No repinta — quien llama
        decide cuándo hacerlo."""
        self._entrada_expandida = False
        self.entrada.max_lines = LINEAS_COLAPSADA
        self.boton_expandir.content = _icono(ft.Icons.UNFOLD_MORE, 16, "#756b5e")
        self.boton_expandir.tooltip = "Ver todo el mensaje"

    def _on_cambio_entrada(self, evento):
        """Enciende y apaga los dos botones de la derecha según lo escrito:
        el de enviar en cuanto hay algo que mandar, el de desplegar solo
        cuando el texto ya no cabe en la caja. Corre en cada tecla, así que
        sale temprano cuando ninguno de los dos cambió, para no repintar de
        más."""
        texto = self.entrada.value or ""
        hay_texto = bool(texto.strip())
        desborda = self._lineas_estimadas(texto) > LINEAS_COLAPSADA

        if (
            hay_texto == self.boton_enviar.visible
            and desborda == self.boton_expandir.visible
        ):
            return

        self.boton_enviar.visible = hay_texto
        self.boton_expandir.visible = desborda
        if not desborda:
            # El dueño borró texto hasta que volvió a caber: la caja se
            # pliega sola, si no quedaría alta y medio vacía.
            self._plegar_entrada()
        self._refrescar()

    def _alternar_expansion(self, evento):
        if self._entrada_expandida:
            self._plegar_entrada()
        else:
            self._entrada_expandida = True
            self.entrada.max_lines = LINEAS_EXPANDIDA
            self.boton_expandir.content = _icono(ft.Icons.UNFOLD_LESS, 16, "#756b5e")
            self.boton_expandir.tooltip = "Contraer"
        self._refrescar()

    # ------------------------------------------------------------------
    # Enviar / responder
    # ------------------------------------------------------------------
    def _enviar_mensaje(self, evento):
        if self._procesando:
            return
        texto = (self.entrada.value or "").strip()
        if not texto:
            return

        if not self._modo_chat:
            self._montar_chat()

        self._contador_preguntas += 1
        clave = f"pregunta-{self._contador_preguntas}"
        fila = self._fila(self._burbuja_usuario(texto), derecha=True)
        fila.key = ft.ScrollKey(clave)
        self.lista_mensajes.controls.append(fila)

        self.entrada.value = ""
        self.boton_expandir.visible = False
        self.boton_enviar.visible = False
        self._plegar_entrada()
        self._refrescar()
        self.router.page.run_task(self._responder, texto, clave)

    def _quitar_indicador(self, indicador: ft.Control):
        """Quita la fila de "Pensando..." SI todavía está puesta.

        Parece defensivo de más y no lo es: los tres caminos de _responder
        lo hacían con un .remove() pelón, y eso escondió un fallo real el
        2026-09-06. Si algo truena DESPUÉS de haber quitado el indicador
        —por ejemplo al construir la burbuja de la respuesta— el except
        intenta quitarlo otra vez, list.remove levanta ValueError, esa
        segunda excepción se lleva por delante al except entero y la
        burbuja roja de error NUNCA se llega a agregar. Resultado en
        pantalla: la pregunta se queda sola, sin respuesta y sin aviso de
        nada, que es justo lo que vio el desarrollador y lo que le costó
        grabar un video para poder reportarlo.
        """
        if indicador in self.lista_mensajes.controls:
            self.lista_mensajes.controls.remove(indicador)

    async def _responder(self, pregunta: str, clave: str):
        self._procesando = True
        self.entrada.disabled = True
        indicador = self._fila(self._burbuja_pensando(), derecha=False)
        self.lista_mensajes.controls.append(indicador)
        self._refrescar()
        # Nada que arrancar: el logo es un WebP animado y lo reproduce el
        # cliente. Tampoco hay nada que detener al terminar — la fila se
        # quita de la conversación y con ella se va la animación.
        await self._ir_a(clave)

        try:
            if self._ia is None:
                self._ia = IAController()
            respuesta = await asyncio.to_thread(
                self._ia.preguntar, pregunta, self._historial
            )
            self._quitar_indicador(indicador)
            self.lista_mensajes.controls.append(
                self._fila(self._burbuja_ia(respuesta), derecha=False)
            )
            # Solo se guarda en el historial DESPUÉS de una respuesta exitosa
            # — si la llamada falló, no queremos que una pregunta sin
            # respuesta quede colada en la conversación que se le manda al
            # modelo la próxima vez.
            self._historial.append({"role": "user", "content": pregunta})
            self._historial.append({"role": "assistant", "content": respuesta})
        except RuntimeError as error:
            # Típicamente el OPENAI_API_KEY faltante — ver IAController.__init__.
            self._quitar_indicador(indicador)
            self.lista_mensajes.controls.append(
                self._fila(self._burbuja_error(str(error)), derecha=False)
            )
        except Exception:
            # traceback a consola a propósito: aquí caen tanto los fallos de
            # red (que el dueño ve como el aviso rojo y ya) como los errores
            # de programación, y estos últimos no deben desaparecer sin
            # dejar rastro — ver _quitar_indicador.
            traceback.print_exc()
            self._quitar_indicador(indicador)
            self.lista_mensajes.controls.append(
                self._fila(
                    self._burbuja_error(
                        "No se pudo conectar con el agente de IA. Intenta de nuevo."
                    ),
                    derecha=False,
                )
            )
        finally:
            self._procesando = False
            self.entrada.disabled = False
            self._refrescar()
            # Se vuelve a mandar el scroll a la pregunta y no al final de
            # todo: así la respuesta se empieza a leer desde arriba.
            await self._ir_a(clave)
            # Y el cursor regresa a la caja: al deshabilitarla mientras la IA
            # pensaba, el campo perdió el foco, y sin esto el dueño tendría
            # que volver a hacer clic para escribir la siguiente pregunta.
            try:
                await self.entrada.focus()
                # El realce se marca a mano y NO se deja al evento: medido en
                # la ventana real, un focus() programático mueve el cursor
                # pero NO dispara on_focus (ni en escritorio ni en web). Sin
                # esto la caja se quedaba plana con el cursor ya dentro —
                # lista para escribir pero sin verse así — hasta que el dueño
                # hiciera clic. El on_blur del usuario la apaga igual que
                # siempre, así que las dos rutas siguen de acuerdo.
                self._entrada_enfocada = True
                self._aplicar_realce_caja()
                self._refrescar()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    def _refrescar(self):
        """self.update() a prueba de que el dueño haya navegado a otra
        pantalla mientras la IA respondía: la vista ya no está montada y
        flet levanta una excepción que, dentro de la tarea de _responder,
        no la vería nadie."""
        try:
            self.update()
        except (RuntimeError, AssertionError):
            pass

    async def _ir_a(self, clave: str):
        """Desplaza la conversación hasta dejar esa pregunta hasta arriba."""
        # Un respiro para que flet alcance a pintar el control nuevo: sin
        # esto el desplazamiento se calcula con la lista todavía sin él.
        await asyncio.sleep(0.08)
        try:
            await self.lista_mensajes.scroll_to(scroll_key=clave, duration=260)
        except Exception:
            pass
