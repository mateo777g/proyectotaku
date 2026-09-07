"""Genera el wordmark "TAKU / MONKY" para los anuncios de la Fase 7, en sus
2 variantes de color (blanco y naranja de marca), con assets/logo-emblema.png
sustituyendo la O de MONKY -- igual que en los mockups assets/img1-4.png.

Por que existe como script y no como PNG suelto sin origen: si algun dia
cambia la fuente, el emblema o la proporcion del badge, esto se vuelve a
correr en vez de rehacer el diseño a mano en un editor de imagenes. Mismo
principio que generar_logo_pensando.py con el WebP animado.

LA FUENTE: Lovelo (la que usan los 4 mockups) NO se metio a este repo --
no esta en esta maquina y su licencia es gratis solo para uso PERSONAL,
mientras que este panel se le renta a otros restaurantes (ver Fase 7,
trampa #5 en el roadmap). En su lugar se usa League Spartan Black,
Google Fonts / SIL Open Font License (assets/fuentes/LeagueSpartan-Black.ttf
+ su OFL.txt), la primera de la lista de alternativas que el propio roadmap
proponia por si Lovelo no se pudiera empaquetar -- geometrica, pesada, en
mayusculas, muy cercana a Lovelo Black a simple vista. Si el dueño consigue
una licencia comercial real de Lovelo, cambiar FUENTE por esa ruta y volver
a correr este script es todo lo que hace falta -- nada mas en el proyecto
depende del archivo de fuente en si, solo de los 2 PNG que este script
produce.

Uso:
    python herramientas/generar_wordmark.py
"""
import os

from PIL import Image, ImageDraw, ImageFont

RAIZ = os.path.join(os.path.dirname(__file__), "..")
FUENTE = os.path.join(RAIZ, "assets", "fuentes", "LeagueSpartan-Black.ttf")
EMBLEMA = os.path.join(RAIZ, "assets", "logo-emblema.png")

TAM_FUENTE = 300          # resolucion de trabajo; el resultado se recorta al
                          # bbox real y queda a este tamaño nativo (los
                          # llamadores lo reducen con .thumbnail(), igual que
                          # ya hace logo-emblema.png)
NARANJA_MARCA = (0xF4, 0x88, 0x0A, 255)
BLANCO = (255, 255, 255, 255)

# cuanto mas grande es el emblema que sustituye la O, respecto a la altura
# de mayusculas de la propia fuente -- >1 para que se lea como una insignia
# y no como una letra plana, igual que en los mockups
FACTOR_INSIGNIA = 1.30
# separacion entre el renglon TAKU y el renglon MONKY, como fraccion de la
# altura de mayusculas
FACTOR_ENTRELINEA = 0.10


def _medir():
    return ImageDraw.Draw(Image.new("RGB", (1, 1)))


def construir(color_letras, ruta_salida):
    fuente = ImageFont.truetype(FUENTE, TAM_FUENTE)
    d = _medir()
    emblema = Image.open(EMBLEMA).convert("RGBA")

    bbox_m = d.textbbox((0, 0), "M", font=fuente)
    cima, base = bbox_m[1], bbox_m[3]
    alto_mayusculas = base - cima

    ancho_taku = d.textlength("TAKU", font=fuente)

    ancho_m = d.textlength("M", font=fuente)
    ancho_n = d.textlength("N", font=fuente)
    ancho_k = d.textlength("K", font=fuente)
    ancho_y = d.textlength("Y", font=fuente)
    diametro_emblema = round(alto_mayusculas * FACTOR_INSIGNIA)
    ancho_monky = ancho_m + diametro_emblema + ancho_n + ancho_k + ancho_y

    ancho_lienzo = round(max(ancho_taku, ancho_monky))
    entrelinea = round(alto_mayusculas * FACTOR_ENTRELINEA)
    # cuanto se sale el emblema por arriba/abajo de la caja de mayusculas
    saliente = round((diametro_emblema - alto_mayusculas) / 2)

    alto_lienzo = saliente + alto_mayusculas + entrelinea + alto_mayusculas + saliente

    lienzo = Image.new("RGBA", (ancho_lienzo, alto_lienzo), (0, 0, 0, 0))
    draw = ImageDraw.Draw(lienzo)

    # renglon 1: TAKU
    y1 = saliente - cima
    draw.text((0, y1), "TAKU", font=fuente, fill=color_letras)

    # renglon 2: MONKY, con el emblema en vez de la O
    y2_arriba = saliente + alto_mayusculas + entrelinea
    y2 = y2_arriba - cima
    draw.text((0, y2), "M", font=fuente, fill=color_letras)
    x = ancho_m
    emblema_ajustado = emblema.resize((diametro_emblema, diametro_emblema),
                                       Image.LANCZOS)
    y_emblema = y2_arriba - saliente
    lienzo.alpha_composite(emblema_ajustado, (round(x), round(y_emblema)))
    x += diametro_emblema
    draw.text((round(x), y2), "N", font=fuente, fill=color_letras)
    x += ancho_n
    draw.text((round(x), y2), "K", font=fuente, fill=color_letras)
    x += ancho_k
    draw.text((round(x), y2), "Y", font=fuente, fill=color_letras)

    lienzo = lienzo.crop(lienzo.getbbox())
    lienzo.save(ruta_salida)
    print(f"{os.path.basename(ruta_salida)} -> {lienzo.size}")


def main():
    construir(BLANCO, os.path.join(RAIZ, "assets", "logo-wordmark-blanco.png"))
    construir(NARANJA_MARCA,
              os.path.join(RAIZ, "assets", "logo-wordmark-naranja.png"))


if __name__ == "__main__":
    main()
