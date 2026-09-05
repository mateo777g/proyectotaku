"""
panel_licencias/conexion.py
Abrir la sesión de Supabase de UN cliente, y traducir los errores a español
de pantalla.

Cada cliente es un proyecto de Supabase distinto, así que cada uno necesita su
PROPIO supabase.Client con su propia sesión — no hay un cliente compartido
como en models/supabase_client.py. Las sesiones no se pisan entre instancias
de Client (cada una guarda la suya en su propia memoria).

Siempre con la ANON KEY del cliente + login del usuario de LICENCIAS. Nunca
service_role: esa llave se salta el RLS entero, y justamente el chiste de este
panel es que sus credenciales, si se filtran, no sirvan para tocar los
platillos/ventas/fotos de nadie.

conectar() es BLOQUEANTE a propósito (mismo criterio que los DAO del panel de
Taku Monky): quien lo llama lo envuelve en asyncio.to_thread.
"""
import httpx
from supabase import Client, create_client
from supabase_auth.errors import AuthApiError


class LoginFallido(Exception):
    pass


def conectar(cliente: dict) -> Client:
    """Crea el Client de ese proyecto y le hace login. Devuelve el Client ya
    con sesión viva (es de ahí de donde salen los permisos, no de la llave)."""
    supa = create_client(cliente["url"], cliente["anon_key"])
    respuesta = supa.auth.sign_in_with_password(
        {"email": cliente["correo"], "password": cliente["password"]}
    )
    if not respuesta.session:
        raise LoginFallido("Supabase no devolvió sesión.")
    return supa


def traducir_error(err: Exception, momento: str) -> str:
    """Mensaje corto para enseñar EN la fila. `momento` es 'conectar' o
    'leer'/'guardar', solo para que el texto diga en qué se atoró."""
    if isinstance(err, (AuthApiError, LoginFallido)):
        return "Correo o contraseña incorrectos para este proyecto."
    if isinstance(err, httpx.ConnectError):
        # Un proyecto gratis pausado por inactividad cae aquí: el subdominio
        # deja de resolver/responder.
        return "No responde. ¿Proyecto pausado, URL mal escrita o sin internet?"
    if isinstance(err, httpx.RequestError):
        return "No hay conexión con este proyecto. Revisa tu internet."
    texto = str(err).strip().replace("\n", " ")
    if len(texto) > 120:
        texto = texto[:117] + "..."
    return f"Falló al {momento}: {texto}"
