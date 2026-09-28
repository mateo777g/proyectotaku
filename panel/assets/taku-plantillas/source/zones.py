"""Taku Monky — placement zones for the Pillow compositor.

Emits zones.json: for every template and format, the boxes where the
logo, headline, subline and dish photo belong. All values are pixels in
the final canvas, so Pillow can use them directly.

Anchors:
  center  -> (x, y) is the centre of the box
  top     -> y is the top edge, x the horizontal centre
"""
import json
from templates import FORMATS, REF_W, BOX_W, BOX_H, STRIPE_W

OUT = "../zones.json"


def build(fmt):
    w, h = FORMATS[fmt]
    # Ojo: tiene que ser el MISMO eje que templates.scaled() (ancho/REF_W),
    # nunca alto/REF_H -- las dos plantillas son 1080 de ancho y el diseño
    # es width-driven (ver el docstring de scaled() en templates.py). Usar
    # el alto aqui fue el bug real de la Fase 7.0: en "story" (1920 de alto
    # contra un REF_H de 1350) daba s=1.4222 mientras templates.py seguia
    # usando s=1, y las zonas quedaban ~42% más grandes que los elementos
    # reales -- medido: la placa del logo se salia 49px por lado y 92px por
    # abajo, y el safe_area de 01-topografico invadia el fondo blanco.
    s = w / REF_W
    bw, bh = BOX_W * s, BOX_H * s
    bx = (w - bw) / 2

    # the logo sits inside the plate with even padding
    pad = 30 * s
    logo = {
        "x": round(bx + pad), "y": round(pad * 1.4),
        "w": round(bw - pad * 2), "h": round(bh - pad * 2.4),
        "anchor": "box",
    }

    stripe_w = STRIPE_W * s
    stripe_x = (w - stripe_w) / 2

    common_photo = {
        "cx": round(w / 2), "cy": round(h * 0.70),
        "max_w": round(w * 0.86), "max_h": round(h * 0.46),
        "anchor": "center",
    }

    return {
        "01-topografico": {
            "canvas": [w, h],
            "safe_area": [round(stripe_x), 0, round(stripe_w), h],
            "logo": {"x": round(stripe_x + 40 * s), "y": round(60 * s),
                     "w": round(stripe_w - 80 * s), "h": round(210 * s),
                     "anchor": "box"},
            "headline": {"cx": round(w / 2), "cy": round(h * 0.40),
                         "max_w": round(stripe_w - 60 * s),
                         "size": round(74 * s), "color": "#FFFFFF",
                         "anchor": "center"},
            "subline": None,
            "photo": common_photo,
        },
        "02-naranja": {
            "canvas": [w, h],
            "logo": logo,
            "headline": {"cx": round(w / 2), "cy": round(h * 0.345),
                         "max_w": round(w * 0.88),
                         "size": round(104 * s), "color": "#FFFFFF",
                         "anchor": "center"},
            "subline": {"cx": round(w / 2), "cy": round(h * 0.455),
                        "max_w": round(w * 0.78),
                        "size": round(42 * s), "color": "#FFFFFF",
                        "anchor": "center"},
            "photo": common_photo,
        },
        "03-blanca": {
            "canvas": [w, h],
            "logo": logo,
            "headline": {"cx": round(w / 2), "cy": round(h * 0.345),
                         "max_w": round(w * 0.88),
                         "size": round(104 * s), "color": "#F4880A",
                         "anchor": "center"},
            "subline": {"cx": round(w / 2), "cy": round(h * 0.455),
                        "max_w": round(w * 0.78),
                        "size": round(42 * s), "color": "#F4880A",
                        "anchor": "center"},
            "photo": common_photo,
        },
        "04-negra": {
            "canvas": [w, h],
            "logo": logo,
            # this layout repeats the headline as a stacked block
            "headline_stack": {
                "cx": round(w / 2),
                "y0": round(h * 0.315),
                "line_h": round(96 * s),
                "repeats": 7,
                "max_w": round(w * 0.92),
                "size": round(96 * s),
                "color": "#F4880A",
                "anchor": "center",
            },
            "subline": None,
            "photo": {"cx": round(w / 2), "cy": round(h * 0.66),
                      "max_w": round(w * 0.84), "max_h": round(h * 0.42),
                      "anchor": "center"},
        },
    }


def main():
    data = {fmt: build(fmt) for fmt in FORMATS}
    data["_palette"] = {"orange": "#F4880A", "white": "#FFFFFF",
                        "black": "#000000"}
    json.dump(data, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
