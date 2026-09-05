"""
panel_licencias/clientes.py
Lee el archivo de credenciales de los clientes.

DÓNDE VIVE Y POR QUÉ AHÍ: en %LOCALAPPDATA%\\PanelLicencias\\clientes.json, o
sea FUERA del repo — misma idea que sesion.json y huerfanos_r2.json del panel
de Taku Monky. Este repo es PÚBLICO en GitHub y este archivo trae la URL, la
anon key, el correo y la CONTRASEÑA del usuario de licencias de cada cliente.
Nunca debe acabar dentro de la carpeta del proyecto (aunque clientes.json
también está en .gitignore, por si acaso).

QUIÉN LO ESCRIBE: el desarrollador, a mano, cuando da de alta un cliente
nuevo. Este panel SOLO LO LEE. Dar de alta un cliente (crear su proyecto de
Supabase, correr el schema, crear su usuario de licencias) es trabajo aparte
que no hace este programa.

Formato: una lista de objetos, cada uno con los 5 campos de CAMPOS.

Si el archivo no existe o está mal escrito, esto NO truena: o levanta
ArchivoDeClientesInvalido con un mensaje que se pueda enseñar en pantalla tal
cual, o devuelve los renglones buenos + una lista de avisos de los malos. La
regla es la misma que en home_view.py: un renglón podrido no puede tumbar a
los demás.
"""
import json
import os
from pathlib import Path

CAMPOS = ("nombre", "url", "anon_key", "correo", "password")

CARPETA = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "PanelLicencias"
RUTA_CLIENTES = CARPETA / "clientes.json"

EJEMPLO = """[
  {
    "nombre": "Taku Monky",
    "url": "https://xxxxxxxx.supabase.co",
    "anon_key": "eyJhbGciOi...",
    "correo": "licencias@ejemplo.com",
    "password": "la-contrasena-del-usuario-de-licencias"
  }
]"""


class ArchivoDeClientesInvalido(Exception):
    """El archivo entero no se pudo usar (no existe, no es JSON, no es lista).

    Distinto de un renglón mal escrito: eso se reporta como aviso y los demás
    renglones siguen funcionando.
    """


def cargar_clientes() -> tuple[list[dict], list[str]]:
    """Devuelve (clientes_buenos, avisos).

    `avisos` son textos ya redactados para enseñar en pantalla, uno por
    renglón que se tuvo que ignorar.
    """
    if not RUTA_CLIENTES.exists():
        raise ArchivoDeClientesInvalido(
            f"No existe {RUTA_CLIENTES}.\n\n"
            "Créalo a mano con este formato:\n\n" + EJEMPLO
        )

    try:
        crudo = json.loads(RUTA_CLIENTES.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        raise ArchivoDeClientesInvalido(
            f"{RUTA_CLIENTES} no es JSON válido: {err.msg} "
            f"(línea {err.lineno}, columna {err.colno}).\n\n"
            "Suele ser una coma de más al final, o comillas curvas en vez de "
            'comillas rectas (").'
        ) from err
    except OSError as err:
        raise ArchivoDeClientesInvalido(
            f"No se pudo leer {RUTA_CLIENTES}: {err}"
        ) from err

    if not isinstance(crudo, list):
        raise ArchivoDeClientesInvalido(
            f"{RUTA_CLIENTES} debe traer una LISTA de clientes (entre "
            "corchetes), no un solo objeto.\n\n" + EJEMPLO
        )

    clientes: list[dict] = []
    avisos: list[str] = []

    for i, fila in enumerate(crudo, start=1):
        etiqueta = f"Renglón #{i}"
        if not isinstance(fila, dict):
            avisos.append(f"{etiqueta}: no es un objeto {{...}}. Se ignoró.")
            continue

        nombre = str(fila.get("nombre") or "").strip()
        if nombre:
            etiqueta = f'Renglón #{i} ("{nombre}")'

        faltantes = [c for c in CAMPOS if not str(fila.get(c) or "").strip()]
        if faltantes:
            avisos.append(
                f"{etiqueta}: le falta(n) {', '.join(faltantes)}. Se ignoró."
            )
            continue

        url = str(fila["url"]).strip().rstrip("/")
        if not url.startswith("http"):
            avisos.append(
                f'{etiqueta}: la url debe empezar con https:// (dice "{url}"). '
                "Se ignoró."
            )
            continue

        clientes.append(
            {
                "nombre": nombre,
                "url": url,
                "anon_key": str(fila["anon_key"]).strip(),
                "correo": str(fila["correo"]).strip(),
                "password": str(fila["password"]),
            }
        )

    return clientes, avisos
