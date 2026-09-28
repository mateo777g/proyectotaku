"""
models/plantillas.py
Catálogo de las 4 plantillas publicitarias de la Fase 7 (creación de
contenido).

Lee assets/taku-plantillas/zones.json UNA sola vez, al importar este
módulo -- no en cada pantalla ni en cada anuncio generado, porque las
plantillas no cambian en caliente: son las mismas 8 combinaciones
diseño×formato desde que se generaron en la Fase 7.0 (mismo motivo por el
que herramientas/generar_fondos_plantillas.py rasteriza los 8 fondos una
sola vez a png-final/ en vez de invocar Playwright cada vez que se genera
un anuncio).

Sin Pillow y sin flet, igual que models/tiempo.py: esto es solo datos --
qué plantillas hay, qué campos de texto pide cada una, dónde está su
miniatura y dónde está su fondo ya rasterizado. Quien SÍ usa Pillow para
componer el anuncio es models/generador_anuncios.py (Fase 7.2, todavía sin
construir); quien SÍ usa flet para pintar el selector es
views/contenido_view.py (Fase 7.3, todavía sin construir). Ninguno de los
dos debe volver a leer zones.json por su cuenta -- este catálogo es la
única puerta.

Ver CLAUDE.md -> "Creación de contenido (Fase 7)" y el roadmap -> bloque
"FASE 7" para el porqué de cada campo; en particular:
  · trampa #1 (ya arreglada en la 7.0): zones.json venía mal en "story"
    porque zones.py escalaba por el eje equivocado. Este archivo confía en
    zones.json tal cual está hoy porque esa trampa ya se cerró -- si algún
    día vuelve a romperse, se rompe en zones.py/zones.json, no aquí.
  · trampa #6: el formulario de texto cambia según la plantilla -- 01 solo
    pide "headline" (y trae "safe_area", que NO es un campo de texto: es
    una restricción de layout); 02 y 03 piden "headline" + "subline"; 04 no
    usa "headline" sino "headline_stack" (una frase que se repite 7 veces).
    Formato.campos_texto es la respuesta a esa trampa.
"""
import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Optional

# La raíz del repo, un nivel arriba de esta carpeta -- mismo patrón que
# supabase_client.py usa para encontrar el .env sin depender de desde dónde
# se haya lanzado "python main.py".
_RUTA_BASE = Path(__file__).resolve().parent.parent
_RUTA_ZONES = _RUTA_BASE / "assets" / "taku-plantillas" / "zones.json"

# Ruta relativa a la raíz del repo, NO un Path absoluto -- a propósito, y
# por la misma razón que "assets/sin-foto.png"/"assets/logo-pensando.webp"
# en el resto del proyecto son strings sueltos: la app siempre corre con la
# raíz del repo como cwd ("python main.py", ver "Running the app" en
# CLAUDE.md), así que esta misma ruta le sirve tal cual tanto a flet
# (Image.src, con assets_dir=".") como a Pillow (Image.open()) en la 7.2 --
# no hay que resolverla dos veces para dos consumidores distintos.
_RUTA_FONDOS_FINALES = "assets/taku-plantillas/png-final"

# herramientas/generar_fondos_plantillas.py rasterizó los 8 fondos a este
# factor sobre el lienzo de referencia (1080 de ancho) -- ver la Fase 7.0
# en el roadmap, bloque "EL 4K". Es la MISMA idea que ESCALA en ese script,
# repetida aquí porque este catálogo necesita saber el tamaño real del PNG
# sin abrirlo con Pillow (que este archivo no usa). Si el dueño pide más
# nitidez en la 7.6, ese script sube su propia constante ESCALA y regenera
# png-final/ -- y esta constante tiene que subir exactamente igual, o el
# catálogo va a decir que los fondos miden lo que ya no miden. Mismo tipo
# de trampa que CACHE_DURACION_MS en catalogo.js: dos números que solo
# sirven si se mueven juntos.
ESCALA_FONDOS = 2

# id de zones.json -> nombre bonito, para pintarlo en contenido_view.py.
_NOMBRES_PLANTILLA = {
    "01-topografico": "Topográfico",
    "02-naranja": "Naranja",
    "03-blanca": "Blanca",
    "04-negra": "Negra",
}

# id de zones.json -> mockup terminado ("LOS MOCKUPS DE LLEGADA" en el
# roadmap: img1..img4 son las 4 plantillas ya compuestas, en ese mismo
# orden). Hoy contenido_view.py los usa como miniatura de relleno; con este
# catálogo siguen siendo la miniatura correcta, ya no de relleno.
_MINIATURAS_PLANTILLA = {
    "01-topografico": "assets/img1.png",
    "02-naranja": "assets/img2.png",
    "03-blanca": "assets/img3.png",
    "04-negra": "assets/img4.png",
}

# Orden fijo en el que se pintan las 4 plantillas y los 2 formatos --
# zones.json es un dict, y aunque json.load ya preserva el orden de
# inserción del archivo, mejor no dejar que algo que se ve en pantalla
# dependa de eso.
_ORDEN_PLANTILLAS = ("01-topografico", "02-naranja", "03-blanca", "04-negra")
_ORDEN_FORMATOS = ("post", "story")
_NOMBRES_FORMATO = {"post": "Post", "story": "Historia"}

# Público, para que contenido_view.py/generador_anuncios.py iteren los
# formatos sin volver a escribir la lista a mano.
FORMATOS = _ORDEN_FORMATOS


@dataclass(frozen=True)
class ZonaCaja:
    """Un rectángulo anclado por su esquina superior izquierda (x, y) más
    su tamaño (w, h). Lo usan "logo" (anchor="box" en zones.json) y
    "safe_area" (que en zones.json no es un dict con anchor, sino una
    lista [x, y, w, h] plana -- ver _leer_safe_area)."""
    x: int
    y: int
    w: int
    h: int


@dataclass(frozen=True)
class ZonaCentrada:
    """Una caja anclada por su centro (cx, cy) -- la usa "photo": el
    README de assets/taku-plantillas/ la explica como "se mide el
    contenido, se hace thumbnail dentro de (max_w, max_h) y se centra en
    (cx, cy)"."""
    cx: int
    cy: int
    max_w: int
    max_h: int


@dataclass(frozen=True)
class ZonaTexto:
    """Una caja de texto de una sola línea lógica -- "headline" y
    "subline". (cx, cy) es el CENTRO del texto ya medido, no su esquina
    (trampa #7 del roadmap: hay que medir con draw.textbbox() y encoger
    "size" hasta que el texto quepa en max_w antes de restar la mitad para
    ubicarlo)."""
    cx: int
    cy: int
    max_w: int
    size: int
    color: str


@dataclass(frozen=True)
class ZonaTextoRepetido:
    """Exclusiva de "04-negra": headline_stack en vez de headline -- la
    misma frase repetida `repeats` veces, empezando en y0 y bajando
    line_h por renglón, con la foto encima del bloque completo. El dueño
    escribe la frase una sola vez (pregunta ya cerrada en el roadmap:
    "sí, una sola vez y nosotros la repetimos") -- repetirla es trabajo de
    generador_anuncios.py, no de este catálogo."""
    cx: int
    y0: int
    line_h: int
    repeats: int
    max_w: int
    size: int
    color: str


@dataclass(frozen=True)
class Formato:
    """Una plantilla en un formato concreto -- "post" (1080x1350 de
    referencia) o "story" (1080x1920)."""

    id: str
    nombre_bonito: str
    # (ancho, alto) contra el que están escritas las coordenadas de
    # zones.json -- siempre 1080 de ancho, ver "EL 4K" en el roadmap.
    canvas_referencia: tuple
    # (ancho, alto) real del PNG en ruta_fondo, o sea
    # canvas_referencia * ESCALA_FONDOS.
    tamano_final: tuple
    ruta_fondo: str
    logo: ZonaCaja
    photo: ZonaCentrada
    headline: Optional[ZonaTexto]
    subline: Optional[ZonaTexto]
    headline_stack: Optional[ZonaTextoRepetido]
    safe_area: Optional[ZonaCaja]

    @property
    def factor_escala(self) -> float:
        """Cuánto hay que multiplicar una coordenada de zones.json
        (medida contra canvas_referencia) para que caiga en su lugar sobre
        ruta_fondo. Ahorra que generador_anuncios.py repita esta cuenta en
        cada zona que compone."""
        return self.tamano_final[0] / self.canvas_referencia[0]

    @property
    def campos_texto(self) -> list:
        """Qué campos de texto pide este formato, en el orden en que un
        formulario los debe pintar -- la trampa #6 del roadmap. Nunca
        incluye "safe_area": es una restricción de layout (todo el
        contenido debe quedar dentro de esa franja en 01-topografico), no
        algo que el dueño escriba."""
        campos = []
        if self.headline is not None:
            campos.append("headline")
        if self.subline is not None:
            campos.append("subline")
        if self.headline_stack is not None:
            campos.append("headline_stack")
        return campos


@dataclass(frozen=True)
class Plantilla:
    """Una de las 4 plantillas, con sus dos formatos ya resueltos."""

    id: str
    nombre_bonito: str
    ruta_miniatura: str
    formatos: MappingProxyType  # {"post": Formato, "story": Formato}

    @property
    def campos_texto(self) -> list:
        """Los campos de texto que pide esta plantilla -- iguales en
        "post" y en "story" (se valida al cargar el catálogo, ver
        _validar_campos_consistentes), así que contenido_view.py puede
        preguntarlos en el paso 4 sin que el dueño haya elegido formato
        todavía: en el flujo que él pidió, el formato se elige hasta el
        paso 5, después del texto."""
        return self.formatos[_ORDEN_FORMATOS[0]].campos_texto

    def formato(self, id_formato: str) -> Formato:
        """Formato.id -> Formato, con un error legible si no existe."""
        try:
            return self.formatos[id_formato]
        except KeyError:
            raise ValueError(
                f"'{self.id}' no tiene un formato '{id_formato}' -- los "
                f"válidos son {list(_ORDEN_FORMATOS)}."
            ) from None


def _leer_logo(datos: dict) -> ZonaCaja:
    assert datos.get("anchor") == "box", (
        "zones.json cambió el anchor de 'logo' -- este catálogo asume "
        "'box' (esquina superior izquierda); revisa templates.py/"
        "zones.py antes de confiar en las coordenadas."
    )
    return ZonaCaja(x=datos["x"], y=datos["y"], w=datos["w"], h=datos["h"])


def _leer_safe_area(datos: Optional[list]) -> Optional[ZonaCaja]:
    # A diferencia de "logo", en zones.json "safe_area" es una lista plana
    # [x, y, w, h], no un dict con anchor -- así salió de zones.py y no hay
    # razón para tocarlo, es la única zona que no representa un elemento
    # que se dibuja, sino un límite.
    if datos is None:
        return None
    x, y, w, h = datos
    return ZonaCaja(x=x, y=y, w=w, h=h)


def _leer_photo(datos: dict) -> ZonaCentrada:
    assert datos.get("anchor") == "center", (
        "zones.json cambió el anchor de 'photo' -- este catálogo asume "
        "'center'; revisa templates.py/zones.py antes de confiar en las "
        "coordenadas."
    )
    return ZonaCentrada(
        cx=datos["cx"], cy=datos["cy"], max_w=datos["max_w"], max_h=datos["max_h"]
    )


def _leer_zona_texto(datos: Optional[dict]) -> Optional[ZonaTexto]:
    if datos is None:
        return None
    assert datos.get("anchor") == "center", (
        "zones.json cambió el anchor de un headline/subline -- este "
        "catálogo asume 'center'; revisa templates.py/zones.py antes de "
        "confiar en las coordenadas."
    )
    return ZonaTexto(
        cx=datos["cx"],
        cy=datos["cy"],
        max_w=datos["max_w"],
        size=datos["size"],
        color=datos["color"],
    )


def _leer_headline_stack(datos: Optional[dict]) -> Optional[ZonaTextoRepetido]:
    if datos is None:
        return None
    assert datos.get("anchor") == "center", (
        "zones.json cambió el anchor de 'headline_stack' -- este "
        "catálogo asume 'center'; revisa templates.py/zones.py antes de "
        "confiar en las coordenadas."
    )
    return ZonaTextoRepetido(
        cx=datos["cx"],
        y0=datos["y0"],
        line_h=datos["line_h"],
        repeats=datos["repeats"],
        max_w=datos["max_w"],
        size=datos["size"],
        color=datos["color"],
    )


def _leer_formato(id_plantilla: str, id_formato: str, datos: dict) -> Formato:
    ancho_ref, alto_ref = datos["canvas"]
    return Formato(
        id=id_formato,
        nombre_bonito=_NOMBRES_FORMATO[id_formato],
        canvas_referencia=(ancho_ref, alto_ref),
        tamano_final=(ancho_ref * ESCALA_FONDOS, alto_ref * ESCALA_FONDOS),
        ruta_fondo=f"{_RUTA_FONDOS_FINALES}/taku-{id_plantilla}-{id_formato}.png",
        logo=_leer_logo(datos["logo"]),
        photo=_leer_photo(datos["photo"]),
        headline=_leer_zona_texto(datos.get("headline")),
        subline=_leer_zona_texto(datos.get("subline")),
        headline_stack=_leer_headline_stack(datos.get("headline_stack")),
        safe_area=_leer_safe_area(datos.get("safe_area")),
    )


def _validar_campos_consistentes(id_plantilla: str, formatos: dict) -> None:
    """post y story de la MISMA plantilla tienen que pedir el mismo texto
    -- zones.json lo cumple hoy para las 4 (por diseño: las dos son la
    misma composición a distinta altura), pero Plantilla.campos_texto solo
    mira "post" (ver su docstring) para que el paso 4 no tenga que esperar
    a que el dueño elija formato. Si algún día alguien edita zones.json a
    mano, o zones.py vuelve a romperse (la trampa #1 que ya se cerró en la
    7.0), y las dos mitades se desincronizan, mejor que reviente aquí, al
    cargar el catálogo, con un mensaje claro, a que contenido_view.py
    pinte un campo que 7.2 no sepa dónde estampar en el otro formato."""
    referencia = formatos[_ORDEN_FORMATOS[0]].campos_texto
    for id_formato in _ORDEN_FORMATOS[1:]:
        actual = formatos[id_formato].campos_texto
        if actual != referencia:
            raise RuntimeError(
                f"'{id_plantilla}' pide texto distinto según el formato "
                f"({_ORDEN_FORMATOS[0]}={referencia} vs. "
                f"{id_formato}={actual}) -- revisa zones.json."
            )


def _cargar_catalogo() -> dict:
    try:
        crudo = json.loads(_RUTA_ZONES.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise RuntimeError(
            f"No se encontró {_RUTA_ZONES} -- ¿se movió o se borró "
            "assets/taku-plantillas/? Sin ese archivo no hay plantillas "
            "que ofrecer."
        ) from None

    catalogo = {}
    for id_plantilla in _ORDEN_PLANTILLAS:
        formatos = {
            id_formato: _leer_formato(
                id_plantilla, id_formato, crudo[id_formato][id_plantilla]
            )
            for id_formato in _ORDEN_FORMATOS
        }
        _validar_campos_consistentes(id_plantilla, formatos)

        catalogo[id_plantilla] = Plantilla(
            id=id_plantilla,
            nombre_bonito=_NOMBRES_PLANTILLA[id_plantilla],
            ruta_miniatura=_MINIATURAS_PLANTILLA[id_plantilla],
            formatos=MappingProxyType(formatos),
        )
    return catalogo


# Se lee UNA sola vez, al importar -- ver el docstring del módulo. Un
# MappingProxyType/tuple en vez de dict/list "pelones" para que nada
# aguas abajo pueda mutar el catálogo por accidente (agregar una
# plantilla a medias, reordenar los formatos) y que el cambio se cuele
# silenciosamente en otra pantalla.
_CATALOGO = MappingProxyType(_cargar_catalogo())
PLANTILLAS = tuple(_CATALOGO[id_plantilla] for id_plantilla in _ORDEN_PLANTILLAS)


def obtener_plantillas() -> list:
    """Las 4 plantillas, en el orden en que se deben pintar."""
    return list(PLANTILLAS)


def obtener_plantilla(id_plantilla: str) -> Plantilla:
    """Una plantilla por su id ("01-topografico", etc.), con un error
    legible si no existe -- para cuando contenido_view.py recibe el id
    que el dueño eligió en el paso 1 y hay que resolverlo a datos reales."""
    try:
        return _CATALOGO[id_plantilla]
    except KeyError:
        raise ValueError(
            f"No existe la plantilla '{id_plantilla}' -- las válidas son "
            f"{list(_ORDEN_PLANTILLAS)}."
        ) from None
