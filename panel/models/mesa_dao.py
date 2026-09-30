"""
models/mesa_dao.py
Acceso a la tabla public.mesas (Fase 5.1) — el catálogo fijo de mesas del
negocio, que el dueño administra desde el panel (views/mesas_view.py) y que
mesas.html usa para pintar la lista de mesas con su estado (disponible/
ocupada) en vez del campo de texto libre que tenía antes.

Mismo patrón que models/platillo_dao.py: no se atrapan excepciones aquí
(ni de red ni de la API), y actualizar()/eliminar() revisan que `data` no
venga vacío antes de dar por buena la escritura — ver el docstring largo de
platillo_dao.py para el porqué completo (UPDATE/DELETE bloqueado por RLS
"tiene éxito" con data=[] en vez de lanzar un error).
"""
from models.supabase_client import client


class EscrituraSinEfecto(Exception):
    """Ver la clase homónima en platillo_dao.py — mismo significado aquí."""


class CuentasSinMover(Exception):
    """La mesa SÍ se renombró, pero sus cuentas abiertas se quedaron con el nombre viejo
    (ventas.mesa es texto libre, no llave foránea). Quien llame debe avisarlo: esas cuentas
    ya no aparecen en mesas.html hasta que se corrijan."""


_COLUMNAS = "id, nombre, orden"


class MesaDAO:
    @staticmethod
    def obtener_todos() -> list[dict]:
        """Todas las mesas, en el orden en que se deben mostrar tanto en el
        panel como en mesas.html."""
        respuesta = (
            client.from_("mesas").select(_COLUMNAS).order("orden").order("id").execute()
        )
        return respuesta.data or []

    @staticmethod
    def _siguiente_orden() -> int:
        """Mismo mecanismo que PlatilloDAO._siguiente_orden(): una mesa
        nueva siempre cae al final de la lista."""
        respuesta = (
            client.from_("mesas").select("orden").order("orden", desc=True).limit(1).execute()
        )
        filas = respuesta.data or []
        if not filas:
            return 1
        return int(filas[0]["orden"] or 0) + 1

    @staticmethod
    def crear(nombre: str) -> dict:
        fila = {"nombre": nombre, "orden": MesaDAO._siguiente_orden()}
        respuesta = client.from_("mesas").insert(fila).execute()
        if not respuesta.data:
            raise EscrituraSinEfecto("El insert de mesas no devolvió ninguna fila.")
        return respuesta.data[0]

    @staticmethod
    def actualizar(id_mesa: int, nombre: str) -> dict:
        """Solo renombra — no toca `orden` (no hay todavía una forma de
        reordenar mesas a mano, igual que platillos antes de tener un drag
        and drop; se puede agregar después si hace falta).

        Las cuentas ABIERTAS de la mesa se llevan el nombre nuevo: ventas.mesa es texto libre
        y mesas.html/Inicio/esta vista las emparejan con el catálogo por nombre, así que sin
        esto la cuenta queda huérfana (nadie la puede cobrar desde mesas.html). Las cerradas
        conservan su nombre de ese día. Si la mesa se renombró pero las cuentas no se pudieron
        mover, lanza CuentasSinMover."""
        anterior = (
            client.from_("mesas").select("nombre").eq("id", id_mesa).execute()
        ).data or []
        respuesta = (
            client.from_("mesas").update({"nombre": nombre}).eq("id", id_mesa).execute()
        )
        if not respuesta.data:
            raise EscrituraSinEfecto(
                f"El update de mesas id={id_mesa} no afectó ninguna fila."
            )
        if anterior and anterior[0]["nombre"] != nombre:
            try:
                MesaDAO._mover_cuentas_abiertas(anterior[0]["nombre"], nombre)
            except Exception as error:
                raise CuentasSinMover(str(error)) from error
        return respuesta.data[0]

    @staticmethod
    def _mover_cuentas_abiertas(nombre_viejo: str, nombre_nuevo: str) -> None:
        # Mismo emparejamiento que el resto del sistema (_normalizar_mesa), por eso se filtra
        # aquí y no con un .eq() exacto en la consulta. Import local: ia_controller importa
        # este módulo.
        from models.ia_controller import _normalizar_mesa

        clave = _normalizar_mesa(nombre_viejo)
        abiertas = (
            client.from_("ventas").select("id, mesa").eq("estado", "abierta").execute()
        ).data or []
        ids = [v["id"] for v in abiertas if _normalizar_mesa(v.get("mesa")) == clave]
        if not ids:
            return
        respuesta = (
            client.from_("ventas").update({"mesa": nombre_nuevo}).in_("id", ids).execute()
        )
        if len(respuesta.data or []) != len(ids):
            raise EscrituraSinEfecto(
                f"Se movieron {len(respuesta.data or [])} de {len(ids)} cuentas abiertas."
            )

    @staticmethod
    def eliminar(id_mesa: int) -> None:
        """Borra la mesa del catálogo. OJO: esto NO toca ventas.mesa — esa
        columna es un snapshot de texto (ver CLAUDE.md, Fase 5), así que una
        venta ya cerrada con esa mesa se queda intacta con su nombre tal
        cual quedó escrito, aunque la mesa se borre de este catálogo
        después. La vista es responsable de confirmar antes de llamar
        aquí, igual que con PlatilloDAO.eliminar()."""
        respuesta = client.from_("mesas").delete().eq("id", id_mesa).execute()
        if not respuesta.data:
            raise EscrituraSinEfecto(
                f"El delete de mesas id={id_mesa} no afectó ninguna fila."
            )
