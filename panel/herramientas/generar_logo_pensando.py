"""Genera assets/logo-pensando.webp a partir de los 36 SVG de assets/svg/.

    python herramientas/generar_logo_pensando.py

Por qué existe: la pantalla del agente NO anima el logo cuadro por cuadro
desde python. Lo hacía, y se veía congelada en cuanto la máquina se ponía a
trabajar — que es siempre en esa pantalla, porque mientras el logo gira el
mismo proceso lee 4 tablas de Supabase, arma el prompt y espera a OpenAI.
Ver el bloque de la Fase 6 en CLAUDE.md. Ahora es un solo WebP animado que
el cliente reproduce solo, y este script es lo que lo fabrica.

Cómo lo hace, que tiene un truco: los SVG se rasterizan con el propio motor
de flet (se pintan en una rejilla de 6x6 y se captura la ventana), porque no
hay ningún rasterizador de SVG instalado en este entorno y, de paso, así el
resultado sale idéntico a como la app los pintaría. La captura no trae canal
alfa, así que se hace DOS VECES, sobre blanco y sobre negro, y el alfa se
despeja de las dos: sobre negro C = a*F, sobre blanco C = a*F + (1-a), o sea
a = 1 - (blanco - negro). Sin eso el logo saldría con un cuadro de fondo
pegado y solo serviría sobre el crema exacto de esa pantalla.
"""
import asyncio
import os
import subprocess
import sys

LADO = 128          # px por cuadro en el archivo final (se muestra a 42)
COLS = 6
CUADROS = 36
MS_POR_CUADRO = 70  # 36 x 70 ms = ~2.5 s por vuelta, el ritmo del diseño
CALIDAD = 90

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESTINO = os.path.join(RAIZ, "assets", "logo-pensando.webp")


def _rejilla(fondo: str, salida: str):
    """Pinta los 36 SVG en una rejilla sobre `fondo` y guarda la captura."""
    import flet as ft

    async def main(page: ft.Page):
        page.bgcolor = fondo
        page.padding = 0
        page.window.width = LADO * COLS + 40
        page.window.height = LADO * (CUADROS // COLS) + 60
        filas = [
            ft.Row(
                spacing=0,
                controls=[
                    ft.Image(
                        src=f"assets/svg/fragmentless-orange-frame{f * COLS + c:02d}.svg",
                        width=LADO, height=LADO, fit=ft.BoxFit.CONTAIN,
                    )
                    for c in range(COLS)
                ],
            )
            for f in range(CUADROS // COLS)
        ]
        foto = ft.Screenshot(
            content=ft.Container(
                ft.Column(filas, spacing=0), bgcolor=fondo,
                width=LADO * COLS, height=LADO * (CUADROS // COLS),
            ),
            expand=False,
        )
        page.add(foto)
        await asyncio.sleep(3.0)   # que alcance a pintar los 36 SVG
        with open(salida, "wb") as f:
            f.write(await foto.capture(pixel_ratio=1.0))
        os._exit(0)

    ft.run(main, assets_dir=".")


def main():
    # Cada rasterizado abre su propia ventana de flet, así que van en
    # subprocesos: dos ft.run() en el mismo proceso no conviven.
    if len(sys.argv) == 3 and sys.argv[1] == "--rejilla":
        os.chdir(RAIZ)
        _rejilla(sys.argv[2], os.path.join(RAIZ, f"_rej_{sys.argv[2][1:]}.png"))
        return

    import numpy as np
    from PIL import Image

    caminos = {}
    for fondo in ("#ffffff", "#000000"):
        print(f"rasterizando sobre {fondo} ...")
        subprocess.run([sys.executable, os.path.abspath(__file__), "--rejilla", fondo],
                       check=True, cwd=RAIZ)
        caminos[fondo] = os.path.join(RAIZ, f"_rej_{fondo[1:]}.png")

    b = np.asarray(Image.open(caminos["#ffffff"]).convert("RGB")).astype(np.float64) / 255
    n = np.asarray(Image.open(caminos["#000000"]).convert("RGB")).astype(np.float64) / 255
    alfa = np.clip(1.0 - (b - n).mean(axis=2), 0, 1)
    color = np.zeros_like(n)
    visible = alfa > 0.003
    for c in range(3):
        color[..., c][visible] = np.clip(n[..., c][visible] / alfa[visible], 0, 1)

    rgba = Image.fromarray(
        np.dstack([(color * 255).round(), (alfa * 255).round()]).astype(np.uint8), "RGBA"
    )
    lado = rgba.width // COLS
    cuadros = [
        rgba.crop((c * lado, f * lado, (c + 1) * lado, (f + 1) * lado))
        for f in range(CUADROS // COLS)
        for c in range(COLS)
    ]
    cuadros[0].save(DESTINO, save_all=True, append_images=cuadros[1:],
                    duration=MS_POR_CUADRO, loop=0, quality=CALIDAD, method=6)
    for p in caminos.values():
        os.remove(p)
    print(f"listo: {DESTINO} ({os.path.getsize(DESTINO) // 1024} KB, {len(cuadros)} cuadros)")


if __name__ == "__main__":
    main()
