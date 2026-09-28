"""Taku Monky — background patterns, drawn as clean vectors.

seigaiha
    In the real motif each fan OCCLUDES the fans behind it, so only a
    clean crown of every fan is ever visible. Painting every full arc on
    top of every other is what produced the cluttered, spiky look: the
    lower flanks of the back rows poked through the front rows. Here each
    fan is clipped to its own half-disc and rows are emitted back to
    front, so the front row hides what should be hidden.

topographic
    Long contour lines that wander right across the canvas, the way a
    real contour map reads, rather than a few fat concentric blobs.
"""
import math, random

ORANGE = "#F4880A"


# ---------------------------------------------------------------- seigaiha

def seigaiha(w, h, stroke, color, bg, unit=300, rings=4, opacity=1.0,
             y0=0, uid="a"):
    """Seigaiha waves, built the way the real motif is built.

    Each fan is a full set of concentric half-circles. A fan is hidden by
    the fans in FRONT of it, which is reproduced by painting, for every
    fan, first a solid half-disc in the background colour (erasing what
    is behind) and then that fan's arcs on top. Rows are emitted from the
    back forwards, so the occlusion falls out naturally and no stray
    arc ends are left poking through.

    unit   horizontal distance between fan centres in a row; the fan
           radius is half of it, so neighbours meet exactly.
    rings  concentric arcs per fan.
    bg     the colour behind the pattern, used for the occluding discs.
    """
    radius = unit / 2.0
    ring_gap = radius / rings
    # Rows overlap heavily: each row sits only a third of a radius below
    # the last, so a fan covers most of the two fans behind it and only a
    # crown of them survives.
    row_step = radius * 0.34
    cols = int(w / unit) + 3
    rows = int((h - y0) / row_step) + 6

    body = []
    for r in range(rows):
        cy = y0 + r * row_step
        offset = (unit / 2.0) if (r % 2) else 0.0
        for c in range(-1, cols):
            cx = c * unit + offset
            # 1. erase whatever sits behind this fan
            body.append(
                f'<path fill="{bg}" stroke="none" '
                f'd="M {cx - radius:.1f},{cy:.1f} '
                f'A {radius:.1f},{radius:.1f} 0 0 1 {cx + radius:.1f},{cy:.1f} Z"/>'
            )
            # 2. draw this fan's arcs on the cleared ground
            for k in range(1, rings + 1):
                rad = k * ring_gap
                body.append(
                    f'<path fill="none" stroke="{color}" '
                    f'stroke-width="{stroke}" stroke-linecap="round" '
                    f'd="M {cx - rad:.1f},{cy:.1f} '
                    f'A {rad:.1f},{rad:.1f} 0 0 1 {cx + rad:.1f},{cy:.1f}"/>'
                )

    return f'<g opacity="{opacity}">' + "".join(body) + "</g>"


# ------------------------------------------------------------- topographic

def topographic(w, h, stroke, color, seed=7, spacing=34, step=4.0,
                opacity=1.0, dots=True, margin=0.10):
    """Fingerprint / maze pattern: parallel ridges flowing through a field.

    The reference is not a set of contour blobs but a dense ridge field:
    long bands that run side by side, bend in unison, fold back on
    themselves in tight U-turns and stop in rounded tips, with the odd
    isolated dot where a ridge could not fit.

    It is generated the way such patterns actually are: a smooth
    direction field is defined over the canvas, then ridges are traced
    along it one at a time. A new ridge is only kept where it stays at
    least `spacing` away from every ridge already drawn, which is what
    produces the even, woven density and the natural terminations.
    """
    rng = random.Random(seed)

    # --- a smooth direction field, from a few random swirl centres -----
    # Many small, tight swirls rather than a few broad ones: that is what
    # makes ridges turn back on themselves in short U-bends instead of
    # running the length of the canvas like wood grain.
    # A strong base current keeps every ridge flowing broadly the same
    # way; a scattering of weak, medium-sized swirls perturbs it just
    # enough that ridges bend and fold back locally. Too few swirls give
    # wood grain, too many give closed spirals -- this sits between.
    swirls = [(rng.uniform(-0.15, 1.15) * w, rng.uniform(-0.12, 1.12) * h,
               rng.choice((-1, 1)), rng.uniform(0.16, 0.30) * max(w, h))
              for _ in range(11)]
    drift = rng.uniform(0, math.tau)

    def angle_at(x, y):
        ax = math.cos(drift) * 1.55
        ay = math.sin(drift) * 1.55
        for sx, sy, sign, reach in swirls:
            dx, dy = x - sx, y - sy
            d2 = dx * dx + dy * dy + 1.0
            fall = math.exp(-d2 / (reach * reach)) * 0.85
            # rotate the local direction around each swirl centre
            ax += -dy / math.sqrt(d2) * sign * fall
            ay += dx / math.sqrt(d2) * sign * fall
        return math.atan2(ay, ax)

    # --- occupancy grid, so ridges keep their distance cheaply ---------
    cell = spacing / 2.0
    gw = int(w / cell) + 4
    gh = int(h / cell) + 4
    grid = [[] for _ in range(gw * gh)]

    def too_close(x, y, limit):
        gx, gy = int(x / cell) + 2, int(y / cell) + 2
        if gx < 0 or gy < 0 or gx >= gw or gy >= gh:
            return False
        rad = int(limit / cell) + 1
        for iy in range(max(0, gy - rad), min(gh, gy + rad + 1)):
            row = iy * gw
            for ix in range(max(0, gx - rad), min(gw, gx + rad + 1)):
                for px, py in grid[row + ix]:
                    if (px - x) ** 2 + (py - y) ** 2 < limit * limit:
                        return True
        return False

    def occupy(x, y):
        gx, gy = int(x / cell) + 2, int(y / cell) + 2
        if 0 <= gx < gw and 0 <= gy < gh:
            grid[gy * gw + gx].append((x, y))

    pad = margin * min(w, h)

    def trace(x0, y0, direction):
        """Walk the field from a seed until the ridge must stop."""
        pts = []
        x, y = x0, y0
        for _ in range(120):
            if not (-pad < x < w + pad and -pad < y < h + pad):
                break
            if too_close(x, y, spacing * 0.92):
                break
            pts.append((x, y))
            a = angle_at(x, y)
            x += math.cos(a) * step * direction
            y += math.sin(a) * step * direction
        return pts

    ridges = []
    attempts = 0
    target = int((w * h) / (spacing * spacing) * 0.30)
    while len(ridges) < target and attempts < target * 40:
        attempts += 1
        sx = rng.uniform(-pad, w + pad)
        sy = rng.uniform(-pad, h + pad)
        if too_close(sx, sy, spacing):
            continue
        fwd = trace(sx, sy, 1.0)
        back = trace(sx, sy, -1.0)
        line = list(reversed(back[1:])) + fwd
        if len(line) < 3:
            continue
        for px, py in line:
            occupy(px, py)
        ridges.append(line)

    parts = [f'<g fill="none" stroke="{color}" stroke-width="{stroke}" '
             f'stroke-linecap="round" stroke-linejoin="round" '
             f'opacity="{opacity}">']

    for line in ridges:
        if len(line) < 8:
            if dots:
                px, py = line[len(line) // 2]
                parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" '
                             f'r="{stroke * 0.6:.1f}" fill="{color}" '
                             f'stroke="none"/>')
            continue
        d = f"M {line[0][0]:.1f},{line[0][1]:.1f}"
        for px, py in line[1::2]:
            d += f" L {px:.1f},{py:.1f}"
        parts.append(f'<path d="{d}"/>')

    parts.append("</g>")
    return "\n".join(parts)


# ------------------------------------------------------------------ spark

def spark(cx, cy, s, color):
    """The little three-tick spark that sits above the logo."""
    ticks = [(-30, 6, -12, -6), (-4, -14, 2, -34), (16, -8, 34, -22)]
    parts = [f'<g stroke="{color}" stroke-width="{5.5 * s:.1f}" '
             f'stroke-linecap="round" fill="none">']
    for x1, y1, x2, y2 in ticks:
        parts.append(f'<line x1="{cx + x1 * s:.1f}" y1="{cy + y1 * s:.1f}" '
                     f'x2="{cx + x2 * s:.1f}" y2="{cy + y2 * s:.1f}"/>')
    parts.append("</g>")
    return "\n".join(parts)


def rounded_box(x, y, w, h, r, fill, corners="bottom"):
    """A plate with rounded bottom corners and square top corners,
    matching the logo plate that hangs off the top edge."""
    if corners == "bottom":
        return (f'<path fill="{fill}" d="M {x},{y} L {x + w},{y} '
                f'L {x + w},{y + h - r} A {r},{r} 0 0 1 {x + w - r},{y + h} '
                f'L {x + r},{y + h} A {r},{r} 0 0 1 {x},{y + h - r} Z"/>')
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}"/>'
