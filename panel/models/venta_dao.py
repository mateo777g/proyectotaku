"""
models/venta_dao.py
Acceso de solo lectura a public.ventas y public.venta_items — capa DAO para
el agente de IA (Fase 6, ver models/ia_controller.py) y para cualquier otra
pantalla que en el futuro necesite leer el historial de ventas del sistema
de mesas (Fase 5).

Es DELIBERADAMENTE de solo lectura: la escritura de ventas/venta_items vive
en mesas.js (el mesero abre/cierra la venta desde ahí), no en el panel de
Flet — ver CLAUDE.md, Fase 5. Este archivo nunca crea, cierra ni modifica
una venta.

Mismo patrón que platillo_dao.py/mesa_dao.py: no se atrapan excepciones
aquí (ni de red ni de la API) — se dejan subir tal cual a quien llame
(igual que sign_in_with_password en sesion_view.py). Al ser solo lectura,
no hace falta el chequeo de EscrituraSinEfecto que sí necesitan los otros
DAOs (ese problema es específico de UPDATE/DELETE bloqueados por RLS).
"""
from models.supabase_client import client

_COLUMNAS_VENTAS = "id, mesa, estado, total, created_at, updated_at, cerrada_at"
_COLUMNAS_ITEMS = "id, venta_id, platillo_id, nombre, precio_unitario, cantidad, created_at"

# Tope de cuántas ventas se traen para el agente de IA (ver ia_controller.py)
# — no es paginación real, es nada más para que el system prompt no crezca
# sin control conforme pasen los meses. Hoy (Fase 6) el negocio apenas tiene
# un puñado de ventas de prueba, así que esto no recorta nada todavía. Si
# el volumen real algún día se acerca a este número, la solución correcta
# es resumir/agregar en SQL (o acotar por fecha), no subir el número a lo
# bruto — dejarlo anotado aquí para no repetir la discusión después.
_LIMITE_VENTAS_POR_DEFECTO = 500


class VentaDAO:
    @staticmethod
    def obtener_ventas(limite: int = _LIMITE_VENTAS_POR_DEFECTO) -> list[dict]:
        """Ventas más recientes primero (abiertas y cerradas, todas — no
        filtra por estado, a diferencia de mesas.html que sí distingue para
        pintar "Disponible"/"Ocupada")."""
        respuesta = (
            client.from_("ventas")
            .select(_COLUMNAS_VENTAS)
            .order("created_at", desc=True)
            .limit(limite)
            .execute()
        )
        return respuesta.data or []

    @staticmethod
    def obtener_items_de_ventas(ids_venta: list[int]) -> list[dict]:
        """Los renglones de venta_items que pertenecen a esas ventas, en un
        solo IN(...) en vez de una consulta por venta — mismo criterio de
        no hacer N+1 requests que ya sigue el resto del proyecto."""
        if not ids_venta:
            return []
        respuesta = (
            client.from_("venta_items")
            .select(_COLUMNAS_ITEMS)
            .in_("venta_id", ids_venta)
            .order("venta_id")
            .order("id")
            .execute()
        )
        return respuesta.data or []

    @staticmethod
    def obtener_ventas_con_items(limite: int = _LIMITE_VENTAS_POR_DEFECTO) -> list[dict]:
        """Combina las dos consultas de arriba: cada venta trae su propia
        lista de items ya embebida bajo la llave "items", lista para
        aplanarse a texto en ia_controller.py sin que ese archivo tenga que
        conocer el detalle de las dos tablas ni hacer el join a mano."""
        ventas = VentaDAO.obtener_ventas(limite)
        items_por_venta: dict[int, list[dict]] = {}
        for item in VentaDAO.obtener_items_de_ventas([v["id"] for v in ventas]):
            items_por_venta.setdefault(item["venta_id"], []).append(item)
        for venta in ventas:
            venta["items"] = items_por_venta.get(venta["id"], [])
        return ventas
