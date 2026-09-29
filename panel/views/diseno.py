"""
views/diseno.py
Las piezas del diseño nuevo (28/09): el fondo de manchas, el vidrio, las letras y los iconos.
Nació en el Agente IA y es lo que van a usar las demás vistas cuando se rediseñen. Las reglas
(tamaños, pesos, radios, cuándo va vidrio y cuándo sólido) están en planes/plan panel.txt,
"DISEÑO MANCHAS + VIDRIO"; la maqueta aprobada, en panel/diseno/maquetas-agente-ia/.

Los colores salen de views/tema.py (D.texto, D.vidrio...), así que cada pieza se arma con los
del tema que esté puesto al construir la vista.
"""
import flet as ft

from views.tema import D

# Las letras de la maqueta, por peso: Plus Jakarta Sans para todo y JetBrains Mono para las
# etiquetas chicas (fechas, "IDEAS PARA TI", el plan). Flutter no elige el peso de un archivo
# variable, así que cada peso es su propio archivo estático (assets/fuentes/, sacados de los
# variables de Google Fonts con fontTools; licencia OFL al lado). MainController las registra.
FUENTES = {
    "Jakarta400": "assets/fuentes/PlusJakartaSans-Regular.ttf",
    "Jakarta500": "assets/PlusJakartaSans-Medium.ttf",
    "Jakarta600": "assets/fuentes/PlusJakartaSans-SemiBold.ttf",
    "Jakarta700": "assets/PlusJakartaSans-Bold.ttf",
    "Jakarta800": "assets/fuentes/PlusJakartaSans-ExtraBold.ttf",
    "Mono400": "assets/fuentes/JetBrainsMono-Regular.ttf",
    "Mono500": "assets/fuentes/JetBrainsMono-Medium.ttf",
}

# Medidas que se repiten entre piezas (la maqueta, en px).
MARGEN = 16            # del borde de la ventana a la barra, a la barra de arriba y entre ellas
ANCHO_BARRA = 244      # la barra lateral flotante; con sus dos márgenes ocupa 276
ALTO_BARRA_SUPERIOR = 60
DESENFOQUE = 18


def texto(valor, tamano, peso=500, color=None, mono=False, espaciado=None, alto=None, **kwargs):
    """Un texto con la letra de la maqueta. `espaciado` en px (la maqueta lo da en em: 0.14em a
    10.5 px son 1.47 px); `alto` es el interlineado (1.04 del título grande, 1.45 de las
    descripciones)."""
    familia = f"{'Mono' if mono else 'Jakarta'}{peso}"
    estilo = None
    if espaciado is not None or alto is not None:
        estilo = ft.TextStyle(letter_spacing=espaciado, height=alto)
    return ft.Text(valor, size=tamano, font_family=familia, color=color or D.texto,
                   style=estilo, **kwargs)


def etiqueta(valor, tamano=10.5, color=None):
    # Las etiquetas en mayúsculas de la maqueta ("GENERAL", "IDEAS PARA TI", la fecha): mono,
    # separadas 0.14em, en el gris tenue.
    return texto(valor, tamano, 400, color or D.tenue, mono=True, espaciado=round(tamano * 0.14, 2))


def icono(nombre, tamano=18, color=None):
    # Los iconos de trazo de la maqueta (assets/iconos/*.svg, dibujados en negro): el color se
    # les pone tiñéndolos. Nuevo en cada llamada: un icono montado no se cambia, se reemplaza
    # (ver _icono en agenteIA_view.py).
    return ft.Image(src=f"assets/iconos/{nombre}.svg", width=tamano, height=tamano,
                    color=color or D.texto)


def sombra_vidrio():
    return ft.BoxShadow(blur_radius=60, spread_radius=0, color=D.sombra, offset=ft.Offset(0, 24))


def vidrio(contenido=None, radio=22, padding=None, sombra=True, **kwargs):
    """Una superficie de vidrio: el fondo de manchas se ve detrás, desenfocado. Lo llevan la
    barra lateral, la barra de arriba y las tarjetas grandes de cada vista. Lo que se escribe
    o se lee de cerca (la caja de texto, las tarjetas de idea, las tablas) va en sólido.

    ⚠️ La sombra va en un contenedor de afuera, sin blur: flet recorta al borde redondeado
    todo lo de un Container con blur, su propia sombra incluida, y la sombra no se veía."""
    def cristal(**medidas):
        return ft.Container(
            content=contenido,
            blur=ft.Blur(DESENFOQUE, DESENFOQUE),
            bgcolor=D.vidrio,
            border=ft.Border.all(1, D.vidrio_linea),
            border_radius=radio,
            padding=padding,
            **medidas,
        )

    if not sombra:
        return cristal(**kwargs)
    # Medidas y posición (width, expand, top...) van en el de afuera; el cristal lo llena.
    return ft.Container(content=cristal(), border_radius=radio, shadow=sombra_vidrio(), **kwargs)


def fondo_manchas():
    # El fondo animado de todo el panel (herramientas/generar_fondo_manchas.py). Cada píxel del
    # archivo es un puntito: sin filtro (vecino más cercano) salen nítidos.
    return ft.Image(src=D.manchas, fit=ft.BoxFit.COVER, filter_quality=ft.FilterQuality.NONE,
                    gapless_playback=True, left=0, top=0, right=0, bottom=0)


def punto(color, lado=7):
    return ft.Container(width=lado, height=lado, border_radius=lado / 2, bgcolor=color)


def boton(etiqueta_boton, nombre_icono, al_pulsar, principal=False, alto=40):
    """Los botones de la barra de arriba: "Nueva conversación" (principal, en tinta) y los
    secundarios (borde fino, sin relleno). Radio 12, letra 13 semibold, icono 16."""
    color = D.sobre_tinta if principal else D.texto
    cuerpo = ft.Container(
        height=alto,
        padding=ft.Padding.symmetric(horizontal=16 if principal else 14),
        border_radius=12,
        bgcolor=D.tinta if principal else None,
        border=None if principal else ft.Border.all(1, D.linea),
        content=ft.Row([icono(nombre_icono, 16, color), texto(etiqueta_boton, 13, 600, color)],
                       spacing=8, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        on_click=al_pulsar,
        animate_opacity=150,
    )

    def encima(e):
        cuerpo.opacity = 0.86 if e.data in (True, "true") else 1
        cuerpo.update()

    cuerpo.on_hover = encima
    return cuerpo


def insignia(valor):
    # La pastilla naranja de "IA" en la barra.
    return ft.Container(
        bgcolor=D.acento, border_radius=6, padding=ft.Padding.symmetric(horizontal=7, vertical=3),
        content=texto(valor, 10, 400, "#ffffff", mono=True, espaciado=0.4),
    )
