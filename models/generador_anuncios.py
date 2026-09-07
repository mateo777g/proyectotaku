"""
models/generador_anuncios.py
El compositor Pillow de la Fase 7 (creación de contenido) — equivalente de
image_controller.py en "EJEMPLOS 2", pero sin nada de su matemática de
Fortnite (perspectiva, sombras "meta", limpiar_imagen_checker): aquí el
fondo ya es plano y la foto ya viene recortada por rembg (Fase 4.3), así
que componer es puro "pegar capas en su lugar".

Recibe una plantilla + un formato + un platillo (con su
image_url_recortada) + los textos que pida Formato.campos_texto, y
escribe el PNG en biblioteca/ — generar y "guardar en la biblioteca" son
el MISMO acto, tal como pidió el dueño para esta fase (ver "CÓMO SE ARMA"
en el roadmap, bloque "FASE 7"): no hay un paso aparte de guardar.

Sin flet. Todas las funciones públicas de este módulo son SÍNCRONAS y
BLOQUEANTES (Pillow = CPU, la descarga de la foto = red) — mismo
convenio que PlatilloDAO/cloudflare_storage.py: es responsabilidad de
quien llama (views/contenido_view.py, Fase 7.3) mandarlas a un hilo
aparte con asyncio.to_thread. Nada aquí atrapa excepciones tampoco — la
vista decide qué mostrar, igual que en los DAO.

Usa exclusivamente models/plantillas.py para toda la geometría — nunca
vuelve a abrir zones.json. Lo único que agrega sobre ese catálogo es la
lógica de composición que la Fase 7.0 dejó documentada pero sin resolver
a propósito (ver "TRAMPA #2" más abajo).

TRAMPA #2 (destellos vs. caja del logo) — resuelta aquí, no en el
catálogo, porque es lógica de composición, no un dato de la plantilla.
templates.py pinta un pequeño destello de 3 rayitas (spark(), en
assets/taku-plantillas/source/patterns.py) DENTRO de la caja "logo" de
zones.json, y la receta ingenua del README (thumbnail + centrar en la
caja completa) hace que el wordmark lo atraviese en las 4 plantillas —
medido y confirmado con capturas reales en la Fase 7.0. La caja del logo
hay que tratarla como "el hueco que queda ABAJO del destello", así que
_caja_logo_bajo_destello() la recorta por arriba antes de centrar nada
ahí. Los números del destello (posición de su centro por plantilla, y
cuánto se extiende su trazo) salen de spark() misma, no se adivinaron:
ver los comentarios junto a _SPARK_CY_REFERENCIA.

TRAMPA #7 (medir y encoger el texto) — _medir_y_encoger() baja el "size"
hasta que el texto quepa en max_w, midiendo con draw.textbbox() como
pide el README de assets/taku-plantillas/; con anchor="center", (cx, cy)
es el CENTRO del texto ya medido, no su esquina, así que
_dibujar_centrado() resta la mitad del bbox real (no de un tamaño
nominal) antes de posicionar.

TIPOGRAFÍA: League Spartan Black (assets/fuentes/LeagueSpartan-Black.ttf),
no Georgia — Georgia es la fuente del panel, no la de los anuncios (ver
CLAUDE.md → Fase 7). Es la misma fuente que ya usa
herramientas/generar_wordmark.py para las letras del logo, en vez de
Lovelo (licencia personal-only, no empaquetable en un repo público que
además es la base de un producto que se renta — ver trampa #5 del
roadmap). Los mockups (assets/img1-4.png) llevan el texto en MAYÚSCULAS,
así que headline/subline/headline_stack se pasan por .upper() antes de
medirse y dibujarse — es una decisión de este módulo, no algo que
zones.json indique, documentada aquí por si el dueño pide texto mixto
más adelante.
"""
import io
import os
import time

import httpx
from PIL import Image, ImageDraw, ImageFont

from models.plantillas import ZonaCaja, obtener_plantilla

_RUTA_FUENTE = "assets/fuentes/LeagueSpartan-Black.ttf"

# id de plantilla -> wordmark del color correcto para su fondo/placa. 01,
# 03 y 04 tienen la placa/franja del logo en naranja (necesitan letras
# BLANCAS para contrastar); 02 tiene la placa BLANCA (necesita letras
# naranja). Ver herramientas/generar_wordmark.py, que generó los 2 PNG.
_WORDMARK_POR_PLANTILLA = {
    "01-topografico": "assets/logo-wordmark-blanco.png",
    "02-naranja": "assets/logo-wordmark-naranja.png",
    "03-blanca": "assets/logo-wordmark-blanco.png",
    "04-negra": "assets/logo-wordmark-blanco.png",
}

# --- trampa #2: el destello ya pintado en la plantilla ---------------------
# Coordenadas de spark() (assets/taku-plantillas/source/patterns.py),
# medidas contra el lienzo de referencia de 1080 de ancho -- el MISMO en
# post y en story, porque templates.scaled() usa s = ancho/1080 y los dos
# formatos miden 1080 de ancho (s=1 en los dos). No son números adivinados:
#   - templates.py llama spark(bx+120, 100, ...) en 01-topografico y
#     spark(bx+78, 92, ...) en 02/03/04 -- ésa es la cy del centro.
#   - el trazo tiene grosor 5.5px con punta redonda (radio 2.75) y la
#     rayita más baja de las 3 llega a y=+6 respecto al centro, así que el
#     borde inferior REAL del destello queda en cy + 6 + 2.75 = cy + 8.75.
#     Verificado contra las cifras ya medidas en el roadmap (trampa #2):
#     ~x=370..438/y=55..100 en 02-naranja-post, ~y=66..106 en 01-topografico.
_SPARK_CY_REFERENCIA = {
    "01-topografico": 100,
    "02-naranja": 92,
    "03-blanca": 92,
    "04-negra": 92,
}
_SPARK_BORDE_TRAZO = 8.75

# El "margen chico" que pide la trampa #2 entre el destello y el wordmark,
# en el mismo lienzo de referencia de 1080.
_MARGEN_LOGO_DESTELLO = 10

# Pública (no con guion bajo) desde la Fase 7.4: views/biblioteca_view.py
# necesita saber dónde está esta carpeta para poder LISTARLA, no solo
# generador_anuncios.py para escribir en ella -- mismo motivo por el que
# generar y "guardar en la biblioteca" son el mismo acto (ver el docstring
# del módulo): las dos pantallas tienen que estar de acuerdo en un solo
# nombre de carpeta, nunca repetirlo como un string suelto en cada archivo.
RUTA_BIBLIOTECA = "biblioteca"


def _caja_logo_bajo_destello(id_plantilla: str, formato) -> ZonaCaja:
    """La caja "logo" de la plantilla, recortada por ARRIBA para que
    empiece en el borde inferior del destello + el margen chico (trampa
    #2) -- ya escalada al tamaño final del PNG (formato.factor_escala),
    lista para usarse directo contra el fondo rasterizado."""
    logo = formato.logo
    borde_destello = _SPARK_CY_REFERENCIA[id_plantilla] + _SPARK_BORDE_TRAZO
    y_arriba_ref = max(logo.y, borde_destello + _MARGEN_LOGO_DESTELLO)
    y_abajo_ref = logo.y + logo.h

    e = formato.factor_escala
    return ZonaCaja(
        x=round(logo.x * e),
        y=round(y_arriba_ref * e),
        w=round(logo.w * e),
        h=round((y_abajo_ref - y_arriba_ref) * e),
    )


def _pegar_logo(lienzo: Image.Image, plantilla, formato) -> None:
    caja = _caja_logo_bajo_destello(plantilla.id, formato)
    wordmark = Image.open(_WORDMARK_POR_PLANTILLA[plantilla.id]).convert("RGBA")
    wordmark.thumbnail((caja.w, caja.h), Image.LANCZOS)
    x = caja.x + (caja.w - wordmark.width) // 2
    y = caja.y + (caja.h - wordmark.height) // 2
    lienzo.alpha_composite(wordmark, (x, y))


# --- trampa #7: medir y encoger el texto ------------------------------------

def _medir_y_encoger(draw: ImageDraw.ImageDraw, texto: str, tam_inicial: int,
                      max_w: float):
    """Baja "size" de 2 en 2 hasta que `texto` quepa en `max_w`, midiendo
    con draw.textbbox() como pide el README de assets/taku-plantillas/ --
    sin esto un nombre largo ("QUESADILLAS DE CHICHARRÓN PRENSADO") se sale
    del lienzo. No baja de un piso (35% del tamaño pedido) para que un
    texto absurdamente largo termine ilegiblemente chico en vez de
    desaparecer en un tam=0."""
    tam = tam_inicial
    tam_minimo = max(10, round(tam_inicial * 0.35))
    while True:
        fuente = ImageFont.truetype(_RUTA_FUENTE, tam)
        bbox = draw.textbbox((0, 0), texto, font=fuente)
        if bbox[2] - bbox[0] <= max_w or tam <= tam_minimo:
            return fuente, bbox
        tam -= 2


def _dibujar_centrado(draw: ImageDraw.ImageDraw, texto: str, fuente, bbox,
                       cx: float, cy: float, color: str) -> None:
    """(cx, cy) es el CENTRO del bbox real ya medido, no su esquina --
    trampa #7. bbox trae el padding propio de la fuente (bbox[0]/bbox[1]
    no son necesariamente 0), así que hay que restarlo también."""
    ancho, alto = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = cx - ancho / 2 - bbox[0]
    y = cy - alto / 2 - bbox[1]
    draw.text((x, y), texto, font=fuente, fill=color)


def _dibujar_zona_texto(draw: ImageDraw.ImageDraw, zona, texto: str,
                         e: float) -> None:
    texto = texto.strip().upper()
    tam_inicial = round(zona.size * e)
    fuente, bbox = _medir_y_encoger(draw, texto, tam_inicial, zona.max_w * e)
    _dibujar_centrado(draw, texto, fuente, bbox, zona.cx * e, zona.cy * e,
                       zona.color)


def _dibujar_headline_stack(draw: ImageDraw.ImageDraw, zona, texto: str,
                             e: float) -> None:
    """Exclusiva de 04-negra: la MISMA frase repetida `repeats` veces,
    bajando `line_h` por renglón -- el dueño la escribe una sola vez, no
    es un campo que se llene 7 veces (ver ZonaTextoRepetido en
    models/plantillas.py). Se mide/encoge una sola vez, con la fuente ya
    resuelta compartida por las 7 líneas -- si cupiera a tamaños distintos
    por renglón el bloque se vería dentado, y todas las líneas son el
    mismo texto de todos modos."""
    texto = texto.strip().upper()
    tam_inicial = round(zona.size * e)
    fuente, bbox = _medir_y_encoger(draw, texto, tam_inicial, zona.max_w * e)
    cx = zona.cx * e
    for i in range(zona.repeats):
        cy = (zona.y0 + i * zona.line_h) * e
        _dibujar_centrado(draw, texto, fuente, bbox, cx, cy, zona.color)


def _pegar_textos(lienzo: Image.Image, formato, textos: dict) -> None:
    draw = ImageDraw.Draw(lienzo)
    e = formato.factor_escala
    if formato.headline is not None:
        _dibujar_zona_texto(draw, formato.headline, textos["headline"], e)
    if formato.subline is not None:
        _dibujar_zona_texto(draw, formato.subline, textos["subline"], e)
    if formato.headline_stack is not None:
        _dibujar_headline_stack(draw, formato.headline_stack,
                                 textos["headline_stack"], e)


# --- la foto del platillo ---------------------------------------------------

# La imagen recortada (Fase 4.3) es pública en R2 -- httpx.get() sin
# ninguna credencial, verificado en la Fase 7.0 contra las 5 URLs reales.
# Cachear por URL evita rebajar el mismo WebP en cada vista previa que el
# dueño pida dentro de un mismo arranque del panel (el paso 5/6 del
# asistente puede generar varias veces antes de guardarse la que le guste).
_CACHE_FOTOS: dict = {}


def _obtener_foto_recortada(url: str) -> Image.Image:
    if url not in _CACHE_FOTOS:
        respuesta = httpx.get(url, timeout=15.0)
        respuesta.raise_for_status()
        _CACHE_FOTOS[url] = Image.open(io.BytesIO(respuesta.content)).convert("RGBA")
    # .copy(): thumbnail() más abajo modifica la imagen EN SITIO, y la
    # cacheada tiene que quedar intacta para la siguiente vez que se pida.
    return _CACHE_FOTOS[url].copy()


def _pegar_foto(lienzo: Image.Image, formato, foto: Image.Image) -> None:
    zona = formato.photo
    e = formato.factor_escala
    foto.thumbnail((round(zona.max_w * e), round(zona.max_h * e)), Image.LANCZOS)
    x = round(zona.cx * e - foto.width / 2)
    y = round(zona.cy * e - foto.height / 2)
    lienzo.alpha_composite(foto, (x, y))


# --- el nombre del archivo ---------------------------------------------------

_MAPA_ACENTOS = str.maketrans("áéíóúñ", "aeioun")


def _slug(texto: str) -> str:
    texto = texto.strip().lower().translate(_MAPA_ACENTOS)
    limpio = "".join(c if c.isalnum() else "-" for c in texto)
    while "--" in limpio:
        limpio = limpio.replace("--", "-")
    return limpio.strip("-") or "platillo"


def _ruta_salida(platillo: dict, plantilla, formato) -> str:
    slug = _slug(platillo.get("nombre", "platillo"))
    marca_tiempo = int(time.time() * 1000)
    nombre = f"{slug}-{plantilla.id}-{formato.id}-{marca_tiempo}.png"
    # Diagonal explícita, NO os.path.join: en Windows os.path.join produce
    # "biblioteca\archivo.png", y ese backslash rompe ft.Image(src=...) en
    # el cliente de flet (que resuelve assets_dir="." como una URL, donde
    # "\" no es separador) -- se encontró integrando esto con
    # views/contenido_view.py (Fase 7.3), el primer consumidor real que
    # pasa esta ruta directo a un ft.Image. Pillow (open()/save()) y
    # os.makedirs() aceptan "/" en Windows sin ningún problema, así que
    # esto no le cuesta nada al otro consumidor de esta ruta.
    return f"{RUTA_BIBLIOTECA}/{nombre}"


def _validar_textos(formato, textos: dict) -> None:
    esperados = set(formato.campos_texto)
    recibidos = {clave for clave, valor in textos.items() if valor and valor.strip()}
    faltantes = esperados - recibidos
    if faltantes:
        raise ValueError(
            f"Faltan estos campos de texto para '{formato.id}': "
            f"{sorted(faltantes)} -- se esperaban {sorted(esperados)}."
        )


def generar_anuncio(id_plantilla: str, id_formato: str, platillo: dict,
                     textos: dict) -> str:
    """Compone el anuncio y lo guarda en biblioteca/ -- generar y guardar
    son el MISMO acto, no hay un paso aparte (ver el docstring del
    módulo). Devuelve la ruta relativa del PNG ya escrito, lista tanto
    para abrirla en una vista previa de flet (assets_dir="." en main.py,
    igual que image_url/sin-foto.png) como para volver a abrirla con
    Pillow.

    id_plantilla / id_formato: los ids de models/plantillas.py
    ("01-topografico".."04-negra", "post"/"story").
    platillo: el dict de PlatilloDAO -- solo se usan "nombre" (para el
    nombre del archivo) e "image_url_recortada" (la foto a estampar); el
    llamador es responsable de que sea uno de los platillos con recorte
    (PlatilloDAO.contar_platillos_con_recorte() / los ids con recorte).
    textos: dict con las claves que pida Formato.campos_texto -- p. ej.
    {"headline": "...", "subline": "..."} en 02/03, o solo
    {"headline_stack": "..."} en 04-negra (una sola vez: la repetición de
    7 líneas la hace este módulo, no el dueño).
    """
    plantilla = obtener_plantilla(id_plantilla)
    formato = plantilla.formato(id_formato)
    _validar_textos(formato, textos)

    url_foto = platillo.get("image_url_recortada")
    if not url_foto:
        raise ValueError(
            f"El platillo '{platillo.get('nombre', '?')}' no tiene "
            "image_url_recortada -- el paso de elegir platillo solo debe "
            "ofrecer los que sí tienen recorte."
        )

    # Orden de composición, tal como lo pide el roadmap (Fase 7, bloque
    # 7.2): fondo -> logo -> texto -> foto. La foto va AL FINAL a
    # propósito -- en 04-negra queda por diseño encima del bloque de texto
    # repetido (ver el mockup img4.png), y en el resto no se topan porque
    # el texto vive en el tercio de arriba y la foto en el de abajo.
    lienzo = Image.open(formato.ruta_fondo).convert("RGBA")
    _pegar_logo(lienzo, plantilla, formato)
    _pegar_textos(lienzo, formato, textos)
    _pegar_foto(lienzo, formato, _obtener_foto_recortada(url_foto))

    os.makedirs(RUTA_BIBLIOTECA, exist_ok=True)
    ruta = _ruta_salida(platillo, plantilla, formato)
    # RGB, no RGBA: el fondo ya es opaco de punta a punta (alpha_composite
    # sobre una base opaca da alpha=255 en todos lados), así que el canal
    # extra solo pesaría archivo sin aportar nada.
    lienzo.convert("RGB").save(ruta)
    return ruta
