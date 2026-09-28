"""Rasteriza los 8 SVG de assets/taku-plantillas/svg/ al tamaño final con el
que el generador de anuncios (Fase 7.2) va a componer -- ni el 1080x1350
"de trabajo" que ya vive en png/, ni el vectorial en tiempo real.

Por que existe este script y no se rasteriza al vuelo cada vez que se genera
un anuncio: las plantillas no cambian de un anuncio a otro (igual que
generar_logo_pensando.py genera el WebP una sola vez a partir de los SVG
sueltos), y Playwright/Chromium no debe volverse una dependencia de tiempo
de ejecucion del panel -- ver la Fase 7 en el roadmap, bloque "7.0".

ESCALA=2 fue la recomendacion de partida del roadmap (bloque "EL 4K"): a 2x
la foto recortada del platillo (tope real de 1600px desde la Fase 4.3) se
agranda solo 1.33x dentro de la zona "photo" y no se nota. Si el dueño ve un
anuncio real (Fase 7.6) y pide mas nitidez, este numero es lo unico que hay
que subir antes de volver a correr el script -- no hay que tocar los SVG ni
zones.json, que ya escalan solos (ver el docstring de scaled() en
source/templates.py).

Uso:
    python herramientas/generar_fondos_plantillas.py
"""
import asyncio
import glob
import os
import re

from playwright.async_api import async_playwright

ESCALA = 2

RUTA_SVG = os.path.join(os.path.dirname(__file__), "..", "assets",
                         "taku-plantillas", "svg")
RUTA_SALIDA = os.path.join(os.path.dirname(__file__), "..", "assets",
                            "taku-plantillas", "png-final")


async def main():
    archivos = sorted(glob.glob(os.path.join(RUTA_SVG, "*.svg")))
    if not archivos:
        raise SystemExit(f"no se encontraron SVG en {RUTA_SVG}")
    os.makedirs(RUTA_SALIDA, exist_ok=True)

    async with async_playwright() as p:
        navegador = await p.chromium.launch()
        for ruta in archivos:
            svg = open(ruta, encoding="utf-8").read()
            w = int(re.search(r'width="(\d+)"', svg).group(1))
            h = int(re.search(r'height="(\d+)"', svg).group(1))
            pagina = await navegador.new_page(
                viewport={"width": w, "height": h},
                device_scale_factor=ESCALA,
            )
            await pagina.set_content(
                "<style>html,body{margin:0;padding:0}"
                "svg{display:block}</style>" + svg
            )
            destino = os.path.join(
                RUTA_SALIDA,
                os.path.basename(ruta).replace(".svg", ".png"),
            )
            await pagina.screenshot(path=destino)
            await pagina.close()
            print(f"{os.path.basename(destino)} -> {w * ESCALA}x{h * ESCALA}")
        await navegador.close()
    print(f"listo: {len(archivos)} fondos en {RUTA_SALIDA}")


if __name__ == "__main__":
    asyncio.run(main())
