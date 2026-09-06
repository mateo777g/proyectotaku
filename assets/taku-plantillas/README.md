# Taku Monky — plantillas publicitarias

Fondos vacíos para el generador de Pillow. **No traen logo, foto ni texto**:
todo eso lo estampa Python encima.

## Contenido

```
png/    8 plantillas listas para usar (1080x1350 y 1080x1920)
svg/    las mismas en vector — reexporta a cualquier tamaño sin perder nitidez
zones.json   coordenadas de dónde va cada elemento
source/      los scripts que las generan
```

## Las 4 plantillas

| Archivo | Fondo | Patrón | Placa del logo |
|---|---|---|---|
| `01-topografico` | Blanco | Curvas de nivel naranjas | Franja vertical naranja |
| `02-naranja` | Naranja | Ondas blancas | Placa blanca |
| `03-blanca` | Blanco | Ondas naranjas | Placa naranja |
| `04-negra` | Negro | Ondas naranjas arriba, se desvanecen | Placa naranja |

Cada una en `-post` (1080×1350) y `-story` (1080×1920).

## Paleta

| | Hex |
|---|---|
| Naranja marca | `#F4880A` |
| Blanco | `#FFFFFF` |
| Negro | `#000000` |

## Usar zones.json desde Pillow

```python
import json
from PIL import Image

zones = json.load(open("zones.json"))
z = zones["post"]["02-naranja"]          # formato -> plantilla

base = Image.open("png/taku-02-naranja-post.png").convert("RGBA")

# logo: se escala dentro de su caja, centrado
lg = z["logo"]
logo = Image.open("logo.png").convert("RGBA")
logo.thumbnail((lg["w"], lg["h"]), Image.LANCZOS)
base.alpha_composite(
    logo,
    (lg["x"] + (lg["w"] - logo.width) // 2,
     lg["y"] + (lg["h"] - logo.height) // 2),
)

# foto del platillo: se escala y se ancla por el centro
ph = z["photo"]
dish = Image.open("taco.png").convert("RGBA")
dish.thumbnail((ph["max_w"], ph["max_h"]), Image.LANCZOS)
base.alpha_composite(dish, (ph["cx"] - dish.width // 2,
                            ph["cy"] - dish.height // 2))
```

Los campos `headline` y `subline` traen `cx`, `cy`, `max_w`, `size` y `color`.
Ancla `center` significa que `(cx, cy)` es el centro del texto: mide con
`draw.textbbox((0,0), texto, font=f)` y resta la mitad. Si el texto no cabe
en `max_w`, baja `size` hasta que entre.

`04-negra` no usa `headline` sino `headline_stack`: la misma frase repetida
`repeats` veces, empezando en `y0` y bajando `line_h` por línea. La foto va
encima de ese bloque.

`01-topografico` no tiene `subline`, y trae `safe_area`: todo el contenido
debe quedar dentro de esa franja central.

## Regenerar

```bash
cd source
python3 templates.py    # -> svg/
python3 raster.py       # -> png/
python3 zones.py        # -> zones.json
```

Para otro tamaño, agrega la entrada en `FORMATS` dentro de `templates.py`.
El diseño está construido sobre un ancho de referencia de 1080, así que
cualquier lienzo escala solo.

## Notas

Los patrones se redibujaron como vectores, no se reescalaron desde las
imágenes originales. Por eso ya no aparece el difuminado que tenían los
arcos de arriba, y salen nítidos a cualquier resolución.
