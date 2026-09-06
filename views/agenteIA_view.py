import asyncio
import math
import re
import traceback

import flet as ft

from models.ia_controller import IAController, saludo_de_respaldo

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

# Los dos huecos que reparten la pantalla de BIENVENIDA: saludo -> caja y
# caja -> ideas. Están aquí y no de números sueltos en _montar_bienvenida
# porque son lo único que decide si la pantalla se lee aireada o apretada,
# y se afinaron mirando, no calculando.
#
# El de las ideas nació en 26 y el desarrollador lo rebotó de inmediato
# ("está muy pegado todo"), pidiendo la repartición de Claude. Se midió la
# suya contra una captura real —las dos están casi a la misma escala, sus
# ideas van a 48 px una de otra y las nuestras a 50— y ahí ese hueco es de
# ~76 px. NO se copió ese número: en Claude, dentro de esos 76 px va una
# fila de enlaces ("Proyecto o carpeta · Manual") que aquí no existe, así
# que 76 dejaría un vacío en vez de una separación. Renderizando 26/46/58/72
# en la ventana real y comparándolos lado a lado, 58 es donde las ideas ya
# se leen como su propia sección sin despegarse de la caja; en 72 empiezan
# a flotar. El de arriba subió de 34 a 42 por lo mismo — así los dos quedan
# en la proporción de Claude (~45 px del saludo a lo que sigue).
HUECO_SALUDO_CAJA = 42
HUECO_CAJA_IDEAS = 58

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

# El logo fijo que va antes del saludo de bienvenida, como el asterisco de
# Claude. Es UN cuadro suelto de la secuencia, no el WebP animado: aquí no
# se mueve nada, es un adorno. frame35 lo escogió el desarrollador ("esa
# está chida, hay otra más delgada que no"), o sea que si algún día se
# regenera la secuencia hay que volver a mirar cuál cuadro queda mejor —
# no cualquiera sirve, varían de grosor.
RUTA_LOGO_SALUDO = "assets/svg/fragmentless-orange-frame35.svg"
TAMANO_LOGO_SALUDO = 52

# El saludo va en NEGRO, todo. Antes eran dos renglones y el segundo iba en
# naranja (#bf571d); con el logo delante ya hay un elemento naranja en el
# bloque y pintar además el texto de dos colores lo satura. El naranja de
# esta pantalla vive ahora en el logo y en el botón de enviar.
TAMANO_SALUDO = 38

# Lado del logo y tamaño del "Pensando..." de al lado. Fueron subiendo el
# 2026-09-06: 28/13 al montarlo, 36/14 porque a 28 no se alcanzaba a apreciar
# que se movía —que es justo para lo que existe— y 42/14 al llegar la
# secuencia nueva de 36 cuadros. Los dos números viven aquí para que se
# puedan reajustar juntos: si uno crece y el otro no, la fila se desbalancea.
TAMANO_LOGO_PENSANDO = 42
TAMANO_TEXTO_PENSANDO = 14


# ---------------------------------------------------------------------------
# "Ideas para ti" — los tres atajos de la pantalla de bienvenida
# ---------------------------------------------------------------------------
# Texto de reposo de la caja. Es una constante y no un literal suelto porque
# ahora hay dos sitios que lo ponen: el TextField al construirse y
# _hover_idea() al salirse el cursor de una idea. Si se quedara escrito a
# mano en los dos, un cambio en uno dejaría al otro restaurando el viejo.
HINT_ENTRADA = "Escribe una pregunta sobre tu negocio..."

# Fondo que se enciende bajo una idea cuando el cursor pasa encima. Es el
# mismo #f3ead4 que _estilo_markdown() ya usa para las cajas de tabla/cita/
# código, o sea que no entra ningún tono nuevo. Se escogió sobre #f8f1de
# (la superficie de la burbuja y la caja) porque sobre el crema de la vista
# ese apenas se distingue —3, 4 y 11 puntos de diferencia por canal— y un
# realce de hover que no se ve no sirve de nada; #f3ead4 va 8, 11 y 21.
COLOR_IDEA_HOVER = "#f3ead4"

# Los tres atajos. La estructura es la de cualquier chat de IA grande: un
# rótulo corto que se lee de un vistazo, y detrás un prompt largo y preciso
# que el dueño nunca tendría que escribir.
#
# ⚠️ LOS TRES PIDEN EL DESGLOSE POR PRODUCTO Y PROHÍBEN EL DE MESA, a
# propósito. El agente sabe contestar las dos cosas —_resumen_calculado()
# le manda los dos desgloses ya sumados—, pero estos atajos son para la
# pregunta que el dueño se hace de verdad: qué se vendió y cuánto dejó cada
# producto. Por mesa es un dato de operación, no de negocio, y aquí sobra.
#
# ⚠️ LA PRIMERA FRASE DE CADA PROMPT SE BASTA SOLA, y eso no es estilo: el
# prompt se asoma en la caja de texto mientras el cursor está encima de la
# idea (ver _hover_idea), y ahí se corta a UN renglón —unos 74 caracteres—
# porque hint_max_lines=1. Si la parte que dice de qué es el reporte cayera
# en la segunda frase, el dueño vería un adelanto que no dice nada. Si
# alguna vez se reescriben, que lo importante siga cabiendo al principio.
#
# ⚠️ "EL TOTAL NO VA DENTRO DE LA TABLA" TAMPOCO ES UNA MANÍA DE FORMATO, y
# se ganó a pulso. Sin esa frase el modelo cierra la tabla con una fila
# **Total** y, para llenarla, suma la columna de unidades ÉL MISMO: probado
# contra la base real, contestó "21 unidades" donde eran 25 — y 21 resultó
# ser el total de AYER, o sea que ni siquiera se equivocó al sumar, se
# equivocó de periodo y el número se veía perfectamente creíble. El dinero
# de esa misma respuesta sí venía bien, que es lo peor del caso: falla solo
# en la columna que nadie revisa. Sacando el total de la tabla, el modelo ya
# no tiene ninguna columna que sumar y solo copia el total del periodo, que
# le llega precalculado. Del lado de Python el respaldo también está puesto
# (ver el renglón TOTAL POR PRODUCTO en _bloque_desglose de
# models/ia_controller.py), pero esta frase es la que evita que lo necesite.
# Y de paso es lo que pidió el dueño: la tabla y, debajo, cuánto se hizo.
#
# El periodo va en MAYÚSCULAS dentro del prompt porque es lo único que
# cambia entre los tres y es lo que el modelo no debe confundir; el resto
# del texto es idéntico a propósito, para que las tres respuestas salgan
# con la misma forma y se puedan comparar entre sí.
IDEAS = (
    {
        "icono": ft.Icons.TODAY_OUTLINED,
        "titulo": "Qué se vendió hoy",
        "prompt": (
            "Ventas de HOY por producto, en tabla y con el total al final. "
            "Ponme el producto, cuántas unidades se vendieron y cuánto dinero "
            "representa cada uno, de mayor a menor. El total no va dentro de "
            "la tabla: va debajo, en un renglón de texto. No lo desgloses por "
            "mesa."
        ),
    },
    {
        "icono": ft.Icons.DATE_RANGE_OUTLINED,
        "titulo": "Reporte de la semana",
        "prompt": (
            "Ventas de ESTA SEMANA por producto, en tabla y con el total al "
            "final. Ponme el producto, cuántas unidades se vendieron y cuánto "
            "dinero representa cada uno, de mayor a menor. El total no va "
            "dentro de la tabla: va debajo, en un renglón de texto. No lo "
            "desgloses por mesa."
        ),
    },
    {
        "icono": ft.Icons.CALENDAR_MONTH_OUTLINED,
        "titulo": "Reporte del mes",
        "prompt": (
            "Ventas de ESTE MES por producto, en tabla y con el total al "
            "final. Ponme el producto, cuántas unidades se vendieron y cuánto "
            "dinero representa cada uno, de mayor a menor. El total no va "
            "dentro de la tabla: va debajo, en un renglón de texto. No lo "
            "desgloses por mesa."
        ),
    },
)


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


# Hueco entre bloques de markdown (parrafo -> tabla -> lista...). Es el
# block_spacing de _estilo_markdown() sacado a constante porque desde que
# la respuesta se pinta renglon por renglon hay un SEGUNDO sitio que lo
# necesita: _partir_en_renglones() se lo pone a mano a cada renglon que
# empieza un bloque nuevo, que es justo lo que hace que la respuesta
# partida quede pintada igual que la entera. Si cambia aqui, cambia en los
# dos lados a la vez; escrito a mano en cada sitio, no.
ESPACIO_BLOQUE = 12

# Como aparece una respuesta: RENGLON POR RENGLON, de arriba hacia abajo,
# cada uno con un fundido corto, en vez de que el mensaje entero se plante
# de golpe. Lo pidio el desarrollador el 2026-09-06 con un video de Claude
# al lado, y preciso dos veces el detalle que define todo lo demas: la
# animacion va por renglones -"sale un renglon con la animacion, se baja al
# otro y asi"-, no es el bloque completo apareciendo de una. (Primero dijo
# "difuminado"; luego aclaro que se referia a la APARICION de las letras,
# no a un desenfoque. Un desenfoque de verdad si se puede en este flet -un
# Container con blur encima difumina lo que queda debajo, se probo y
# funciona- pero cuesta un BackdropFilter por renglon y no es lo que se
# pidio.)
#
# Los tres numeros estan amarrados entre si y no se tocan por separado:
#
# - PASO_APARICION es cada cuanto ARRANCA el siguiente renglon.
# - DURACION_APARICION es lo que tarda UNO en aparecer, y es a proposito
#   como seis veces el paso: asi siempre hay varios renglones fundiendose
#   al mismo tiempo y la respuesta se lee "de corrido", que es como la
#   pidio el desarrollador. Igualarlos la convertiria en una fila de
#   parpadeos sueltos.
# - PASOS_MAXIMOS es el tope de avisos que python le manda al cliente por
#   respuesta. Con el paso fijo son ~18 por segundo pase lo que pase, pero
#   una respuesta larga tardaria eternidades en acabar de salir; pasado el
#   tope los renglones se revelan de dos en dos o de tres en tres, asi que
#   ninguna respuesta tarda mas de ~1.8 s en terminar de aparecer.
#
# La leccion del logo de "Pensando..." (ver RUTA_LOGO_PENSANDO) NO aplica
# aqui, aunque el ritmo se parezca: ahi python empujaba 14 CUADROS por
# segundo y la animacion se congelaba con la maquina ocupada. Aqui python
# solo manda el disparo de cada renglon y quien interpola el fundido es el
# cliente, con animate_opacity. Si un aviso llega tarde, ese renglon
# arranca tarde pero aparece igual de suave, nunca se queda a medias. Y
# llega cuando la respuesta YA esta en la mano, o sea con el proceso
# desocupado, no mientras se leen 4 tablas y se espera a OpenAI.
PASO_APARICION = 0.055
DURACION_APARICION = 340
PASOS_MAXIMOS = 32

# Lo que sube cada renglon mientras aparece, en fraccion de su propia
# altura (asi mide el offset de flet). Los renglones de texto suben un
# pelin; las tablas, las citas y el codigo NO se mueven, solo se funden:
# al ser mucho mas altos esa misma fraccion los haria dar un brinco de mas
# de 30 px en vez del empujoncito de 6 que se ve en una linea suelta.
SUBIDA_APARICION = 0.25


_RE_TABLA = re.compile(r"^\s*\|")
_RE_TITULO = re.compile(r"^\s{0,3}#{1,6}\s")
_RE_CERCA = re.compile(r"^\s*(```|~~~)")
_RE_CITA = re.compile(r"^\s*>")
_RE_LISTA = re.compile(r"^\s*([-*+]|\d+[.)])\s")
# La fila de guiones que va debajo del encabezado de una tabla. Existe
# porque en GFM los pipes de los extremos son OPCIONALES: el modelo puede
# contestar "Producto | Importe" y debajo "--- | ---", sin un solo pipe al
# principio de renglon. Reconocer la tabla solo por _RE_TABLA dejaria esa
# variante partida renglon por renglon, o sea pintada como basura.
_RE_SEP_TABLA = re.compile(r"^\s*\|?[\s:|-]*-[\s:|-]*\|[\s:|-]*$")
# Un renglon sangrado, que en markdown NO empieza algo nuevo sino que
# continua lo de arriba: una vineta anidada, o un bloque de codigo con
# sangria. Se pega al trozo anterior en vez de volverse uno propio —
# suelto perderia la sangria, y con 4 espacios flutter lo pintaria como
# un bloque de codigo en medio de una lista.
_RE_SANGRIA = re.compile(r"^ {2,}\S")


def _partir_en_renglones(texto: str) -> list:
    """Parte la respuesta en los trozos que van a aparecer uno por uno.

    Devuelve (markdown, hueco_arriba, es_bloque) por trozo. Cada trozo se
    pinta con su PROPIA ft.Markdown, y de ahi salen las dos reglas que
    tiene esta funcion:

    1. UN RENGLON DEL TEXTO = UN TROZO... salvo lo que no se puede partir.
       Una tabla a la que le quites el encabezado deja de ser una tabla y
       se pinta como un monton de pipes; un bloque de codigo sin su cerca
       de cierre, igual. Tablas, codigo y citas se juntan enteros y
       aparecen de un solo fundido - que ademas es lo que se ve bien: una
       tabla saliendo fila por fila se lee como un error de pintado, no
       como una animacion.

    2. EL HUECO SE REPARTE A MANO. Una sola ft.Markdown mete su
       block_spacing entre bloques y NADA entre los renglones de un mismo
       parrafo (los saltos suaves, ver soft_line_break en _burbuja_ia).
       Partida en trozos ese reparto se pierde, asi que aqui se devuelve
       renglon por renglon: ESPACIO_BLOQUE cuando el trozo abre bloque
       nuevo -hubo linea en blanco, o es titulo/lista/tabla/codigo/cita- y
       0 cuando solo continua el parrafo de arriba.

       Los renglones de LISTA cuentan como bloque, y eso NO es un detalle
       de estilo: flutter le mete su block_spacing a cada vineta, asi que
       sin esta regla las listas salian 12 px mas juntas que hoy. Se cacho
       midiendo, no leyendo.

    Que el reparto sea exacto es lo unico que sostiene el cambio: la
    respuesta partida y la entera se renderizaron a 650 px (el ancho real
    de la conversacion) y salieron IDENTICAS pixel por pixel -
    ImageChops.difference dio bbox None, no "casi"-, con una muestra que
    traia titulo, parrafo, tabla (con pipes y sin ellos), negritas,
    vinetas, vinetas anidadas, lista numerada, saltos suaves, cita, regla
    horizontal y codigo. Si algun dia tocas esta funcion, esa es la prueba
    que hay que repetir.
    """
    lineas = texto.replace("\r\n", "\n").split("\n")
    unidades = []
    i = 0
    hubo_blanco = False
    anterior_bloque = False

    while i < len(lineas):
        linea = lineas[i]
        if not linea.strip():
            hubo_blanco = True
            i += 1
            continue

        if unidades and not hubo_blanco and _RE_SANGRIA.match(linea):
            # Continuacion sangrada: se pega al trozo de arriba.
            trozo_previo, hueco_previo, bloque_previo = unidades[-1]
            unidades[-1] = (trozo_previo + "\n" + linea, hueco_previo, bloque_previo)
            i += 1
            continue

        if _RE_CERCA.match(linea):
            # Codigo: de la cerca de apertura a la de cierre. Si el modelo
            # se comio la de cierre, se lleva lo que queda y no se cuelga.
            juntas = [linea]
            i += 1
            while i < len(lineas):
                juntas.append(lineas[i])
                cerro = bool(_RE_CERCA.match(lineas[i]))
                i += 1
                if cerro:
                    break
            trozo, bloque = "\n".join(juntas), True
        elif _RE_TABLA.match(linea) or (
            "|" in linea
            and i + 1 < len(lineas)
            and _RE_SEP_TABLA.match(lineas[i + 1])
        ):
            # Tabla: se junta mientras los renglones lleven pipe, no
            # mientras EMPIECEN con pipe (ver _RE_SEP_TABLA).
            juntas = []
            while i < len(lineas) and lineas[i].strip() and "|" in lineas[i]:
                juntas.append(lineas[i])
                i += 1
            trozo, bloque = "\n".join(juntas), True
        elif _RE_CITA.match(linea):
            juntas = []
            while i < len(lineas) and _RE_CITA.match(lineas[i]):
                juntas.append(lineas[i])
                i += 1
            trozo, bloque = "\n".join(juntas), True
        else:
            trozo = linea
            bloque = bool(_RE_TITULO.match(linea)) or bool(_RE_LISTA.match(linea))
            i += 1

        hueco = ESPACIO_BLOQUE if (hubo_blanco or bloque or anterior_bloque) else 0
        if not unidades:
            # El primer trozo pega con el padding de la burbuja; un hueco
            # aqui lo despegaria del "Pensando..." al que reemplaza.
            hueco = 0
        unidades.append((trozo, hueco, bloque))
        hubo_blanco = False
        anterior_bloque = bloque

    return unidades


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
        # interlineado 1.55, 10 los dejaba pegados entre si. Vive en una
        # constante porque _partir_en_renglones() tiene que reproducir este
        # mismo hueco a mano al pintar la respuesta renglón por renglón.
        block_spacing=ESPACIO_BLOQUE,
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

        # El controlador se crea en la primera llamada que lo necesite —
        # hoy es _cargar_saludo(), que corre al montar la vista, y si esa
        # falla lo vuelve a intentar _responder— en vez de aquí, para que un
        # OPENAI_API_KEY faltante en el .env no reviente la vista al abrir
        # Agente IA — se muestra como
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
            hint_text=HINT_ENTRADA,
            # El texto de reposo se cambia por el prompt de una idea
            # mientras el cursor está encima de ella (ver _hover_idea), y
            # esos prompts miden ~190 caracteres: sin este tope el hint se
            # partiría en 3 renglones, la caja crecería para caberlo y, como
            # en BIENVENIDA todo el bloque va centrado con dos espaciadores,
            # el saludo y las ideas darían un brinco cada vez que el cursor
            # pasa por encima de una. Con 1 renglón la caja no se mueve: el
            # adelanto se corta con puntos suspensivos y ya. Por eso la
            # primera frase de cada prompt tiene que bastarse sola.
            hint_max_lines=1,
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
        # Ideas para ti (solo en el estado de bienvenida)
        # --------------------------------------------------------------
        # Se arma después de caja_entrada porque cada idea, al pasarle el
        # cursor encima, escribe en self.entrada — o sea que la caja tiene
        # que existir ya.
        self.bloque_ideas = self._construir_ideas()

        # --------------------------------------------------------------
        # Saludo (solo en el estado de bienvenida)
        # --------------------------------------------------------------
        # El texto arranca VACÍO y lo llena _cargar_saludo() cuando el
        # modelo contesta (~1 s). Se hace así, y no mostrando una frase de
        # relleno que después se reemplaza, porque ver cambiar el saludo
        # solo se lee como un parpadeo. El bloque no se descuadra mientras
        # tanto: el logo ya le da altura a la fila.
        self.texto_saludo = ft.Text(
            "",
            size=TAMANO_SALUDO,
            font_family="Georgia",
            italic=True,
            color="#18120d",
            text_align=ft.TextAlign.CENTER,
        )
        self.bloque_saludo = ft.Row(
            controls=[
                ft.Image(
                    src=RUTA_LOGO_SALUDO,
                    width=TAMANO_LOGO_SALUDO,
                    height=TAMANO_LOGO_SALUDO,
                    fit=ft.BoxFit.CONTAIN,
                ),
                self.texto_saludo,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=16,
            tight=True,
        )

        self.raiz = ft.Column(
            expand=True,
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self._montar_bienvenida()
        self.content = self.raiz

        # Mismo patrón que home_view.py con sus dos tarjetas: la vista se
        # arma completa y lo que depende de la red se llena después.
        self.router.page.run_task(self._cargar_saludo)

    # ------------------------------------------------------------------
    # Los dos estados de la pantalla
    # ------------------------------------------------------------------
    def _montar_bienvenida(self):
        """Saludo, caja e ideas, centrados. Los dos espaciadores que sobran
        arriba y abajo se reparten el hueco por igual, que es lo que deja el
        bloque justo a la mitad de la pantalla.

        Las ideas viven SOLO aquí y no en la conversación, igual que en los
        chats de IA grandes: en CONVERSACIÓN la caja está anclada abajo, así
        que colgarles tres renglones debajo la subiría a media pantalla y
        además dejaría de tener sentido — para eso ya hay una conversación
        empezada. Como _montar_chat() reescribe raiz.controls, desaparecen
        solas con el primer mensaje; no hay que ocultarlas a mano.
        """
        self.raiz.controls = [
            ft.Container(expand=True),
            self.bloque_saludo,
            ft.Container(height=HUECO_SALUDO_CAJA),
            self.caja_entrada,
            ft.Container(height=HUECO_CAJA_IDEAS),
            self.bloque_ideas,
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
    # Ideas para ti
    # ------------------------------------------------------------------
    def _construir_ideas(self) -> ft.Column:
        """El rótulo + las tres ideas, del mismo ancho que la caja de texto.

        ANCHO_CHAT otra vez, para que las ideas caigan exactamente bajo los
        bordes de la caja en vez de flotar a su aire — la misma razón por la
        que la conversación mide lo mismo.
        """
        controles = [
            # Rótulo con el formato de sección que ya usan menu_view.py
            # ("MI MENÚ"), mesas_view.py ("MESAS") y las tarjetas de
            # home_view.py: 11-13, negritas, café #806f61. La referencia que
            # trajo el desarrollador lo pintaba en gris, pero el gris no
            # existe en esta paleta y este rótulo hace exactamente el mismo
            # trabajo que los otros tres.
            ft.Container(
                content=ft.Text(
                    "IDEAS PARA TI", size=11, weight="bold", color="#806f61"
                ),
                padding=ft.padding.only(left=12, bottom=6),
            ),
        ]
        controles.extend(self._fila_idea(idea) for idea in IDEAS)
        return ft.Column(
            controls=controles,
            # Pegadas entre sí a propósito: el hueco entre una idea y otra lo
            # marca el fondo del hover cuando aparece, no un espacio fijo. Con
            # separación las tres se leerían como tres botones sueltos en vez
            # de como una lista.
            spacing=2,
            width=ANCHO_CHAT,
            tight=True,
        )

    def _fila_idea(self, idea: dict) -> ft.Container:
        """Una idea: cuadrito con icono + rótulo corto, y toda la fila es el
        área sensible (no solo el texto), que es lo que hace que el realce se
        sienta como una lista de verdad y no como tres enlaces."""
        return ft.Container(
            border_radius=12,
            padding=ft.padding.symmetric(horizontal=12, vertical=9),
            content=ft.Row(
                controls=[
                    # Mismo cuadro-con-icono que los atajos de home_view.py,
                    # apretado para una lista de tres renglones: superficie
                    # #f8f1de con borde #eadfca, el mismo par que ya visten
                    # la caja de texto y la burbuja del usuario. Se queda
                    # claro cuando la fila se oscurece al pasar el cursor, y
                    # eso es lo que lo hace resaltar.
                    ft.Container(
                        content=ft.Icon(idea["icono"], size=16, color="#8a7e72"),
                        width=30,
                        height=30,
                        alignment=ft.Alignment(0, 0),
                        bgcolor="#f8f1de",
                        border=ft.border.all(1, "#eadfca"),
                        border_radius=9,
                    ),
                    ft.Text(idea["titulo"], size=14, color="#1c1610", expand=True),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            on_hover=lambda e, prompt=idea["prompt"]: self._hover_idea(e, prompt),
            on_click=lambda e, prompt=idea["prompt"]: self._usar_idea(e, prompt),
        )

    def _hover_idea(self, evento, prompt: str):
        """Con el cursor encima de una idea pasan DOS cosas a la vez: se
        enciende su fondo y la caja de texto adelanta el prompt donde tenía
        su "Escribe una pregunta...". Al salirse, las dos se deshacen.

        Las dos van juntas y no son dos detalles sueltos: el rótulo dice de
        qué es la idea y el adelanto dice qué va a preguntar exactamente, sin
        que el dueño tenga que dar un clic para averiguarlo.

        Escribir el prompt en hint_text y no en value es la parte importante:
        hint_text solo se ve cuando la caja está VACÍA y se pinta en el gris
        apagado del texto de reposo, así que se lee como un adelanto y no
        como algo ya escrito — y si el dueño ya venía escribiendo su propia
        pregunta, ni siquiera se ve, que es justo lo correcto: pasar el
        cursor por encima de algo no debe tocarle lo que lleva tecleado.
        """
        # evento.data es un bool de verdad: True al entrar, False al salir.
        # Medido con mouse real (Playwright sobre el cliente web), no leido
        # de la documentacion — en otras versiones de flet estos eventos
        # llegan como la cadena "true"/"false", que aqui daria siempre True.
        dentro = bool(evento.data)
        evento.control.bgcolor = COLOR_IDEA_HOVER if dentro else None
        self.entrada.hint_text = prompt if dentro else HINT_ENTRADA
        self._refrescar()

    def _usar_idea(self, evento, prompt: str):
        """Un clic en una idea escribe el prompt y lo manda de una vez, sin
        parar en la caja: pedido así explícitamente. La idea ES la pregunta,
        no un borrador — si dejara el texto esperando un Enter, serían dos
        pasos para algo que existe justo para ahorrárselos.
        """
        # El fondo se apaga a mano porque el clic se lleva la fila de la
        # pantalla (_enviar_mensaje monta el estado de CONVERSACIÓN) y con
        # ella se va el on_hover de salida que normalmente lo apagaría.
        evento.control.bgcolor = None
        # Y el hint vuelve al de siempre: _enviar_mensaje deja la caja vacía,
        # o sea que el texto de reposo se vuelve a ver de inmediato. Sin esto
        # se quedaría anunciando el prompt que el dueño acaba de mandar.
        self.entrada.hint_text = HINT_ENTRADA
        self.entrada.value = prompt
        # _enviar_mensaje ya repinta al final, así que no hace falta otro.
        self._enviar_mensaje(evento)

    async def _cargar_saludo(self):
        """Trae el saludo de bienvenida y lo pinta.

        El saludo lo redacta el modelo (ver IAController.saludo), así que
        cambia en cada visita. Si algo falla —no hay OPENAI_API_KEY, no hay
        internet— entra una frase local y el dueño nunca se entera: un
        saludo es decorativo, y sacarle un aviso rojo por eso sería alarmar
        de a gratis. El aviso rojo se queda para cuando falle una pregunta
        de verdad, que es lo que sí le importa.
        """
        try:
            if self._ia is None:
                self._ia = IAController()
            texto = await asyncio.to_thread(self._ia.saludo)
        except Exception:
            # Incluye el RuntimeError de la llave faltante. self._ia se
            # queda en None a propósito: así _responder lo vuelve a
            # intentar y ahí sí enseña el error, que es donde importa.
            texto = saludo_de_respaldo()
        self.texto_saludo.value = texto
        self._refrescar()

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

    def _markdown_respuesta(self, texto: str) -> ft.Markdown:
        """Un trozo de respuesta pintado como markdown.

        El texto va en ft.Markdown y no en ft.Text porque el modelo NO
        contesta en texto pelón: contesta en markdown (**negritas**,
        viñetas, ### encabezados, tablas con pipes). Con ft.Text esos
        símbolos se pintaban crudos. Nada de esto cambia lo que responde el
        modelo ni el prompt de models/ia_controller.py — es solo cómo se
        pinta lo que ya llegaba.

        selectable=True porque las respuestas suelen traer cifras/precios
        que el dueño va a querer copiar.
        """
        return ft.Markdown(
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
        )

    def _renglon_respuesta(self, trozo: str, hueco: int, bloque: bool) -> ft.Container:
        """Un renglón de la respuesta, apagado y listo para encenderse.

        Nace en opacity=0 y lo enciende _revelar(). Quien interpola el
        fundido es el CLIENTE (animate_opacity), no python: python solo
        manda el disparo. Ver PASO_APARICION para por qué eso importa.

        Nacer apagado en vez de ir agregando renglones de uno en uno tiene
        una ventaja que no se ve pero se nota: la respuesta entera ya
        ocupa su alto desde el primer momento, así que el scroll no da
        brincos mientras el texto va saliendo, y _ir_a() calcula bien a
        dónde desplazarse desde el principio.

        La subida solo se le pone a los renglones de texto. Un bloque
        —tabla, código, cita— solo se funde: el offset de flet se mide en
        fracciones de la altura del propio control, así que la misma
        fracción que en una línea de 25 px es un empujoncito de 6, en una
        tabla de 130 px es un brinco de 32.
        """
        animacion = ft.Animation(DURACION_APARICION, ft.AnimationCurve.EASE_OUT)
        return ft.Container(
            content=self._markdown_respuesta(trozo),
            # El hueco va de margen y no de spacing en la Column: es
            # distinto para cada renglón (ver _partir_en_renglones).
            margin=ft.margin.only(top=hueco),
            opacity=0,
            animate_opacity=animacion,
            offset=None if bloque else ft.Offset(0, SUBIDA_APARICION),
            animate_offset=None if bloque else animacion,
        )

    def _burbuja_ia(self, texto: str):
        """La respuesta del agente. Devuelve (contenedor, renglones).

        SIN burbuja, a propósito: la respuesta se pinta directa sobre el
        fondo de la vista, como en Claude/ChatGPT. La del usuario sí
        conserva la suya (#f8f1de + borde #eadfca), y esa diferencia es
        ahora una tercera señal de quién habla, junto al lado y al ancho
        máximo (ver _burbuja_usuario).
        No se pinta bgcolor="#fbf5e9" a mano: un Container sin bgcolor ya
        deja ver el fondo de la vista, y así sigue siendo correcto si ese
        fondo cambia algún día. border_radius también se fue: sin
        superficie ni borde no redondeaba nada.

        La respuesta va partida en un renglón por control en vez de una
        sola ft.Markdown, que es lo que permite que aparezcan uno por uno
        (ver _partir_en_renglones, y _revelar para el encendido). Se
        comprobó que pintada así queda IDÉNTICA píxel por píxel a como
        quedaba entera; la que se ve al final, además, vuelve a ser una
        sola ft.Markdown — ver el final de _revelar().
        """
        renglones = [
            self._renglon_respuesta(trozo, hueco, bloque)
            for trozo, hueco, bloque in _partir_en_renglones(texto)
        ]
        contenedor = ft.Container(
            content=ft.Column(renglones, spacing=0),
            # El padding horizontal es 0 (era 18). Sin una superficie que
            # lo justifique ese hueco solo dejaba el texto de la IA
            # sangrado 18 px respecto al borde izquierdo de la
            # conversación y respecto al "Pensando..." que aparece justo
            # antes en ese mismo sitio, que no lleva padding propio.
            # El vertical se queda en 12 a propósito: sumado al spacing=18
            # de lista_mensajes da exactamente el mismo aire entre
            # mensajes que había cuando la respuesta tenía burbuja.
            padding=ft.padding.symmetric(horizontal=0, vertical=12),
        )
        return contenedor, renglones

    async def _revelar(self, contenedor: ft.Container, renglones: list, texto: str):
        """Va encendiendo los renglones de arriba hacia abajo.

        Corre en su propia tarea, no dentro de _responder: la caja de
        texto ya quedó lista para escribir en cuanto llegó la respuesta y
        no tiene por qué esperar a que acabe de salir el texto. Si el
        dueño manda otra pregunta a medio camino no pasa nada — esta tarea
        solo toca la opacidad de SUS renglones — y si se va a otra
        pantalla, _refrescar() se traga la excepción como siempre.

        De dos en dos o de tres en tres cuando la respuesta es larga: el
        paso está pensado para que se lea de corrido, no para mandarle al
        cliente un aviso por renglón pase lo que pase (ver PASOS_MAXIMOS).

        AL FINAL se cambia la columna de renglones por UNA sola ft.Markdown
        con la respuesta completa, y eso no es limpieza: es lo que
        devuelve la selección de texto de punta a punta. Partida en
        controles, el dueño solo podría seleccionar dentro de un renglón, y
        copiar una tabla entera —justo para lo que selectable=True existe—
        dejaría de funcionar. El cambio es invisible porque las dos formas
        pintan lo mismo píxel por píxel; se hace pasado el fundido del
        último renglón para no cortarlo a media animación.
        """
        por_paso = max(1, math.ceil(len(renglones) / PASOS_MAXIMOS))
        for i in range(0, len(renglones), por_paso):
            for renglon in renglones[i:i + por_paso]:
                renglon.opacity = 1
                if renglon.offset is not None:
                    renglon.offset = ft.Offset(0, 0)
            self._refrescar()
            await asyncio.sleep(PASO_APARICION)

        await asyncio.sleep(DURACION_APARICION / 1000)
        contenedor.content = self._markdown_respuesta(texto)
        self._refrescar()

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

        El naranja es #bf571d, y no es un tono nuevo: venía del segundo
        renglón del saludo, que era naranja hasta que el saludo pasó a ser
        todo negro (2026-09-06). Desde entonces los únicos elementos
        naranjas de la bienvenida son este botón y el logo del saludo.
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

        # Lo que _revelar() necesita para encender la respuesta renglon por
        # renglon. Se declara aqui, fuera del try, porque quien lanza esa
        # tarea es el finally y en los caminos de error no hay nada que
        # animar.
        animacion = None

        try:
            if self._ia is None:
                self._ia = IAController()
            respuesta = await asyncio.to_thread(
                self._ia.preguntar, pregunta, self._historial
            )
            self._quitar_indicador(indicador)
            burbuja, renglones = self._burbuja_ia(respuesta)
            self.lista_mensajes.controls.append(self._fila(burbuja, derecha=False))
            animacion = (burbuja, renglones, respuesta)
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
            # Los renglones nacen apagados, asi que la respuesta se acaba de
            # agregar invisible: esto se lanza ANTES del scroll y del foco
            # para que el texto empiece a salir de inmediato en vez de dejar
            # un hueco en blanco donde estaba el "Pensando...".
            if animacion is not None:
                self.router.page.run_task(self._revelar, *animacion)
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
