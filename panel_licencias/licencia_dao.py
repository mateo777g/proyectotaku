"""
panel_licencias/licencia_dao.py
Acceso a public.configuracion_negocio — pero de UN cliente cualquiera, no del
proyecto de Taku Monky.

POR QUÉ NO SE REUSA models/configuracion_negocio_dao.py: aquel usa el `client`
único y compartido de models/supabase_client.py (un solo proyecto, una sola
sesión, todo @staticmethod). Aquí hay N proyectos abiertos a la vez, cada uno
con su propio Client y su propia sesión, así que este DAO se INSTANCIA con el
cliente que le toca:

    dao = ConfiguracionNegocioDAO(supa)   # supa = create_client(url, anon_key)
    fila = dao.obtener()

Además esta carpeta tiene que ser 100% autocontenida (se va a sacar del repo),
así que no importa nada de models/.

Lo demás es igual que el DAO original, incluido el chequeo de que `data` no
venga vacío en el UPDATE: un UPDATE bloqueado por RLS NO lanza error, devuelve
HTTP 200 con data=[] — o sea "éxito" sin haber tocado nada. Sin este chequeo
el switch de la pantalla se pintaría en verde sin que la licencia haya
cambiado en la base. Ver el docstring largo de models/platillo_dao.py.
"""


class EscrituraSinEfecto(Exception):
    """La escritura "salió bien" pero no afectó ninguna fila (típicamente RLS)."""


_COLUMNAS = "id, nombre, fecha_inicio, fecha_fin, activo"

# Lo único que actualizar() acepta. id/created_at se quedan fuera y updated_at
# lo pone el trigger trg_configuracion_negocio_updated_at, no el cliente.
_CAMPOS_EDITABLES = ("nombre", "fecha_inicio", "fecha_fin", "activo")


class ConfiguracionNegocioDAO:
    def __init__(self, client):
        """`client` es el supabase.Client YA LOGUEADO de ESE cliente
        (ver panel_licencias/conexion.py)."""
        self.client = client

    def obtener(self) -> dict:
        """El renglón único de la tabla de ese proyecto.

        Si no hay ninguno se levanta un error en vez de devolver None: o la
        tabla está vacía (alguien la borró a mano) o esta sesión no tiene
        política de SELECT. Ninguno de los dos es un estado que la tabla del
        panel deba dibujar bonito — es un error de esa fila.
        """
        respuesta = (
            self.client.from_("configuracion_negocio")
            .select(_COLUMNAS)
            .order("id")
            .limit(1)
            .execute()
        )
        filas = respuesta.data or []
        if not filas:
            raise EscrituraSinEfecto(
                "configuracion_negocio no devolvió ninguna fila — o la tabla "
                "está vacía, o este usuario no tiene permiso de leerla (RLS)."
            )
        return filas[0]

    def actualizar(self, datos: dict, id_fila=None) -> dict:
        """Actualiza el renglón con SOLO los campos que vengan en `datos`
        (nombre / fecha_inicio / fecha_fin / activo). Un campo que no venga
        no se toca.

        `id_fila` se puede pasar para ahorrarse un viaje extra a la red: la
        tabla del panel ya trae el id de cuando cargó la fila. Si no viene,
        se busca con obtener().

        Las fechas van como string 'YYYY-MM-DD' o None; la columna es `date`
        y Postgres las castea sola.
        """
        cambios = {k: v for k, v in datos.items() if k in _CAMPOS_EDITABLES}
        if not cambios:
            raise ValueError(
                "actualizar() no recibió ningún campo editable "
                f"(esperaba alguno de {_CAMPOS_EDITABLES})."
            )

        if id_fila is None:
            id_fila = self.obtener()["id"]

        respuesta = (
            self.client.from_("configuracion_negocio")
            .update(cambios)
            .eq("id", id_fila)
            .execute()
        )
        if not respuesta.data:
            raise EscrituraSinEfecto(
                f"El update de configuracion_negocio id={id_fila} no afectó "
                "ninguna fila. Casi siempre es RLS: este usuario puede leer "
                "pero no escribir en ese proyecto."
            )
        return respuesta.data[0]
