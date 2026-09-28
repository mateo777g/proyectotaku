"""
models/config_usuario.py
Configuración del dueño que vive FUERA del repo — hoy solo la ruta
secundaria de exportación que usa views/biblioteca_view.py (Fase 7.4).

NOTA DE ALCANCE, explícita a propósito (pedida así en el prompt de la Fase
7.4 en vez de asumirse en silencio): este archivo NO es la pantalla de
Ajustes. Nació como el pedacito de lógica que hacía falta para que el botón
"Exportar" de la biblioteca funcionara antes de que existiera un lugar en
la UI para elegir esa ruta. Desde la Fase 7.5 (2026-09-06) esa pantalla
(views/ajustes_view.py, con el mismo selector de carpeta por Tkinter que
dialogo_platillo.py ya usa para la foto) ya existe y lee/escribe por AQUÍ
(obtener_ruta_exportacion() / guardar_ruta_exportacion()) — ninguna de las
dos pantallas inventó su propio archivo, tal como pedía el roadmap en el
bloque "FASE 7" → "LOS AJUSTES": "la ruta la consultan DOS pantallas. Vive
en un solo lugar y las dos lo leen." obtener_ruta_exportacion() sigue
cayendo a ~/Downloads cuando el dueño nunca guardó nada (o la ruta
guardada ya no existe en disco) — ver esa función.

DÓNDE SE GUARDA — la pregunta que el roadmap dejó abierta en el bloque
"CÓMO SE ARMA" de la Fase 7 ("LO ÚNICO QUE PROPONGO CAMBIAR" frente a
EJEMPLOS 2, que usa un config.json en la raíz del repo): aquí se sigue la
convención que este proyecto ya sentó en otros tres lugares (sesion.json,
mientras existió; huerfanos_r2.json; panel_licencias/clientes.json) en vez
de esa — la configuración del usuario vive en %LOCALAPPDATA%\\TakuMonky\\,
fuera del repo. Dos razones, no solo la de siempre: (1) es la convención
ya sentada, y (2) este repo es PÚBLICO — un config.json rastreado
publicaría la ruta real de la máquina del dueño en cuanto se hiciera commit
con una ruta ya guardada.

Sin flet y sin Pillow, mismo estilo que models/tiempo.py: es solo datos de
configuración, nada que dependa de la UI.
"""
import json
import os
from pathlib import Path

_NOMBRE_CARPETA = "TakuMonky"
_ARCHIVO_CONFIG = "config.json"
_CLAVE_RUTA_EXPORTACION = "ruta_exportacion"


def _ruta_archivo_config() -> Path:
    base = os.getenv("LOCALAPPDATA") or str(Path.home())
    carpeta = Path(base) / _NOMBRE_CARPETA
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta / _ARCHIVO_CONFIG


def _leer_config() -> dict:
    ruta = _ruta_archivo_config()
    try:
        return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
    except (OSError, json.JSONDecodeError):
        # Un config.json corrupto no debe tumbar el panel -- se trata igual
        # que "el dueño nunca configuró nada", mismo criterio que ya sigue
        # _registrar_huerfano() en cloudflare_storage.py con su propio
        # archivo fuera del repo.
        return {}


def obtener_ruta_exportacion() -> str:
    """La carpeta a la que "Exportar" debe copiar un anuncio. Si el dueño
    nunca configuró una (la 7.5 todavía no existe, así que hoy SIEMPRE es
    el caso), o la que configuró ya no existe en disco (se borró la
    carpeta, era una USB que ya no está conectada), cae a ~/Downloads --
    mismo respaldo que describe el roadmap para descargar_imagen() en
    EJEMPLOS 2. Nunca lanza: siempre hay alguna ruta que devolver, aunque
    ~/Downloads tampoco exista -- en ese caso el propio shutil.copy2() del
    llamador es quien debe fallar y avisar, no esta función."""
    ruta = _leer_config().get(_CLAVE_RUTA_EXPORTACION)
    if ruta and os.path.isdir(ruta):
        return ruta
    return str(Path.home() / "Downloads")


def guardar_ruta_exportacion(ruta: str) -> None:
    """Persiste la ruta elegida. Pensada para llamarse al pulsar "Guardar
    Ajustes" en la 7.5 -- NO en cuanto Tkinter la devuelve -- mismo
    criterio que ya sigue EJEMPLOS 2 (ver el roadmap, "LOS AJUSTES")."""
    config = _leer_config()
    config[_CLAVE_RUTA_EXPORTACION] = os.path.normpath(ruta)
    _ruta_archivo_config().write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )
