"""
models/sesion.py
Guardar / cargar / borrar / restaurar la sesión del admin en disco.

DÓNDE se guarda: FUERA del repo, en la carpeta del usuario
    %LOCALAPPDATA%\\TakuMonky\\sesion.json
Nunca dentro del proyecto: ese archivo trae el refresh_token, que es una
credencial real: fuera del repo es imposible que se suba a git por error.
La contraseña del admin NUNCA se guarda aquí ni en ningún archivo.

Solo se guardan tres campos: access_token, refresh_token y expires_at.
"""
import json
import os
from pathlib import Path
from typing import Optional

_NOMBRE_CARPETA = "TakuMonky"
_NOMBRE_ARCHIVO = "sesion.json"


def _ruta_archivo() -> Path:
    base = os.getenv("LOCALAPPDATA") or str(Path.home())
    carpeta = Path(base) / _NOMBRE_CARPETA
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta / _NOMBRE_ARCHIVO


def guardar(session) -> None:
    """Escribe access_token, refresh_token y expires_at de una Session de
    supabase-py en disco. Se llama tras un login exitoso y cada vez que el
    SDK renueva el token solo, para que sesion.json nunca quede desfasado."""
    datos = {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "expires_at": session.expires_at,
    }
    try:
        _ruta_archivo().write_text(json.dumps(datos), encoding="utf-8")
    except OSError as e:
        print(f"[sesion] no se pudo guardar la sesión en disco: {e}")


def cargar() -> Optional[dict]:
    """Devuelve el dict guardado (access_token/refresh_token/expires_at) o
    None si no hay nada guardado o el archivo está corrupto."""
    ruta = _ruta_archivo()
    if not ruta.exists():
        return None
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        if datos.get("access_token") and datos.get("refresh_token"):
            return datos
        return None
    except (OSError, json.JSONDecodeError) as e:
        print(f"[sesion] no se pudo leer la sesión guardada: {e}")
        return None


def borrar() -> None:
    """Elimina la sesión guardada (cerrar sesión)."""
    try:
        ruta = _ruta_archivo()
        if ruta.exists():
            ruta.unlink()
    except OSError as e:
        print(f"[sesion] no se pudo borrar la sesión: {e}")


def restaurar(client) -> bool:
    """Intenta dejar activa, en `client`, la sesión guardada en disco.

    client.auth.set_session() ya se encarga sola de refrescar el access_token
    si venció (usando el refresh_token); si el refresh también falla lo
    reporta con una excepción. En cualquiera de los dos casos de fallo se
    borra lo guardado y se regresa False, para que el router mande a
    mostrar_login(). Si no hay nada guardado, ni siquiera intenta la red.
    """
    datos = cargar()
    if not datos:
        return False
    try:
        respuesta = client.auth.set_session(
            datos["access_token"], datos["refresh_token"]
        )
        if respuesta.session:
            guardar(respuesta.session)
            return True
        borrar()
        return False
    except Exception as e:
        print(f"[sesion] no se pudo restaurar la sesión guardada: {e}")
        borrar()
        return False
