"""Taku Monky — the four empty advertising templates.

Everything Pillow will later stamp on top (logo, dish photo, headline,
subline) is deliberately absent. These files are backgrounds only.

Geometry is expressed against a 1080x1350 reference and scaled by a
single factor, so the Story build is the same design, just larger.
"""
import os
from patterns import (seigaiha, topographic, spark, rounded_box, ORANGE)

BLACK = "#000000"
WHITE = "#FFFFFF"

REF_W, REF_H = 1080, 1350          # the post format everything is authored in

FORMATS = {
    "post":  (1080, 1350),
    "story": (1080, 1920),
}

# --- measured off the supplied references ------------------------------
BOX_X, BOX_W = 339, 431            # logo plate
BOX_H = 324
BOX_R = 34
STRIPE_X, STRIPE_W = 279, 522      # template 1's vertical band


def head(w, h):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" '
            f'height="{h}" viewBox="0 0 {w} {h}">')


def scaled(fmt):
    """Canvas size plus the uniform scale factor for a format.

    Both formats are 1080 wide, so scaling by height would blow the logo
    plate and the pattern up by 1.42x on Story and push the centre band
    off its proportions. The design is width-driven, so the scale is 1
    and Story simply gets more vertical room -- the same design, taller.
    """
    w, h = FORMATS[fmt]
    s = w / REF_W
    return w, h, s


# ------------------------------------------------------------ template 1

def template_1(fmt):
    """White ground, topographic squiggles, solid orange band down the middle."""
    w, h, s = scaled(fmt)
    bw = STRIPE_W * s
    bx = (w - bw) / 2              # keep the band centred at any width

    parts = [head(w, h),
             '<defs>',
             # the ridges dissolve toward the top edge, so the headline
             # area stays calm and the pattern reads as depth
             '<linearGradient id="topofade" x1="0" y1="0" x2="0" y2="1">',
             '<stop offset="0" stop-color="white" stop-opacity="0"/>',
             '<stop offset="0.22" stop-color="white" stop-opacity="0.55"/>',
             '<stop offset="0.45" stop-color="white" stop-opacity="1"/>',
             '</linearGradient>',
             '<mask id="topomask">',
             f'<rect width="{w}" height="{h}" fill="url(#topofade)"/>',
             '</mask>',
             '</defs>',
             f'<rect width="{w}" height="{h}" fill="{WHITE}"/>',
             '<g mask="url(#topomask)">',
             topographic(w, h, 13 * s, ORANGE, seed=3,
                         spacing=58 * s, step=5.0 * s),
             '</g>',
             f'<rect x="{bx:.1f}" y="0" width="{bw:.1f}" height="{h}" '
             f'fill="{ORANGE}"/>',
             spark(bx + 120 * s, 100 * s, s, WHITE),
             '</svg>']
    return "\n".join(parts)


# ------------------------------------------------------------ template 2

def template_2(fmt):
    """Orange ground, white waves, white logo plate."""
    w, h, s = scaled(fmt)
    bw, bh, r = BOX_W * s, BOX_H * s, BOX_R * s
    bx = (w - bw) / 2

    parts = [head(w, h),
             f'<rect width="{w}" height="{h}" fill="{ORANGE}"/>',
             seigaiha(w, h, 5.4 * s, WHITE, ORANGE, unit=390 * s, rings=4, uid="w"),
             rounded_box(bx, 0, bw, bh, r, WHITE),
             spark(bx + 78 * s, 92 * s, s, ORANGE),
             '</svg>']
    return "\n".join(parts)


# ------------------------------------------------------------ template 3

def template_3(fmt):
    """White ground, orange waves, orange logo plate."""
    w, h, s = scaled(fmt)
    bw, bh, r = BOX_W * s, BOX_H * s, BOX_R * s
    bx = (w - bw) / 2

    parts = [head(w, h),
             f'<rect width="{w}" height="{h}" fill="{WHITE}"/>',
             seigaiha(w, h, 5.4 * s, ORANGE, WHITE, unit=390 * s, rings=4, uid="o"),
             rounded_box(bx, 0, bw, bh, r, ORANGE),
             spark(bx + 78 * s, 92 * s, s, WHITE),
             '</svg>']
    return "\n".join(parts)


# ------------------------------------------------------------ template 4

def template_4(fmt):
    """Black ground. Waves only in the upper band, fading to solid black,
    which is where the big stacked headline goes."""
    w, h, s = scaled(fmt)
    bw, bh, r = BOX_W * s, BOX_H * s, BOX_R * s
    bx = (w - bw) / 2
    band = 430 * s                 # how far down the pattern survives

    parts = [head(w, h),
             '<defs>',
             '<linearGradient id="fade" x1="0" y1="0" x2="0" y2="1">',
             '<stop offset="0" stop-color="white" stop-opacity="1"/>',
             '<stop offset="0.62" stop-color="white" stop-opacity="1"/>',
             '<stop offset="1" stop-color="white" stop-opacity="0"/>',
             '</linearGradient>',
             '<mask id="bandmask">',
             f'<rect x="0" y="0" width="{w}" height="{band:.0f}" '
             f'fill="url(#fade)"/>',
             '</mask>',
             '</defs>',
             f'<rect width="{w}" height="{h}" fill="{BLACK}"/>',
             f'<g mask="url(#bandmask)">',
             seigaiha(w, band, 5.4 * s, ORANGE, BLACK, unit=390 * s, rings=4,
                      opacity=0.95, uid="k"),
             '</g>',
             rounded_box(bx, 0, bw, bh, r, ORANGE),
             spark(bx + 78 * s, 92 * s, s, WHITE),
             '</svg>']
    return "\n".join(parts)


BUILDERS = {
    "01-topografico": template_1,
    "02-naranja": template_2,
    "03-blanca": template_3,
    "04-negra": template_4,
}


def main():
    out = "/home/claude/taku/svg"
    os.makedirs(out, exist_ok=True)
    n = 0
    for name, fn in BUILDERS.items():
        for fmt in FORMATS:
            open(f"{out}/taku-{name}-{fmt}.svg", "w").write(fn(fmt))
            n += 1
    print(f"wrote {n} template SVGs")


if __name__ == "__main__":
    main()
