"""
models/platillo_dao.py
Acceso a la tabla public.platillos — capa DAO, sigue el patrón de VentaDAO
que usa EJEMPLOS/ia_controller.py (VentaDAO.obtener_todas_las_ventas()): una
clase con un método que hace la consulta contra Supabase y regresa los datos
ya listos para pintar, sin lógica de UI aquí.

Fase 2 pasos 2.1-2.5: solo lectura, obtener_todos(). Fase 2.6: se agregan las
operaciones de escritura — crear/actualizar/eliminar/cambiar_visibilidad —
para cablear el botón "Agregar platillo" y los íconos de ojo/lápiz.

No se atrapan excepciones en este archivo: tanto errores de red (httpx,
si Supabase no responde) como errores de la API (postgrest.APIError, por
ejemplo si RLS rechaza algo o un CHECK de la tabla lo rechaza) se dejan subir
tal cual, igual que sign_in_with_password en views/sesion_view.py — es la
vista la que decide qué mensaje mostrar para cada caso.

OJO — esto SÍ se atrapa/convierte aquí, y es la razón de EscrituraSinEfecto
(ver clase abajo): a diferencia de INSERT, un UPDATE o DELETE que RLS bloquea
NO lanza un error de Postgres/PostgREST — simplemente no encuentra ninguna
fila que coincida con la política (WHERE ... AND <política de RLS>) y
"tiene éxito" devolviendo data=[]. Se comprobó en vivo contra Supabase real
en la verificación de la Fase 2.6: con una sesión sin permisos de escritura,
cambiar_visibilidad() devolvía 200 con data=[] y el código original tomaba
eso como éxito, prendiendo el badge OCULTO en pantalla aunque la fila seguía
visible=true en la base — un falso positivo. actualizar/eliminar/
cambiar_visibilidad ahora revisan que `data` no venga vacío y levantan
EscrituraSinEfecto si acaso, para que la vista SÍ se entere y muestre error.
"""
from models.supabase_client import client


class EscrituraSinEfecto(Exception):
    """Supabase respondió sin error pero la escritura no afectó ninguna
    fila — típicamente porque RLS la bloqueó en silencio (ver nota arriba),
    o porque el id ya no existe. Se trata como cualquier otro fallo de
    guardado: la vista la atrapa con el `except Exception` genérico que ya
    tenía y muestra el mismo mensaje amigable de "no se pudo guardar"."""

# Solo las columnas que menu_view.py realmente pinta en la tabla — nunca
# select('*'). Mismo criterio que EJEMPLOS/catalog-cache.js.
# (created_at existe en la tabla pero ninguna vista la usa todavía; "orden"
# tampoco se pinta como texto, solo se usa para el ORDER BY de abajo, así
# que no hace falta traerla también en el select de obtener_todos().)
_COLUMNAS = "id, nombre, descripcion, categoria, precio, visible, image_url"


class PlatilloDAO:
    @staticmethod
    def obtener_todos() -> list[dict]:
        """Trae los platillos ordenados como se muestran en el panel (por
        `orden` y, a igualdad, por `id`) — usa el mismo índice
        platillos_orden_idx que ya existe en la tabla.

        Esto es el panel del ADMIN, no el menú público: RLS deja ver tanto
        los visibles como los ocultos mientras haya una sesión de admin
        activa (ver policy platillos_auth_select en el roadmap). Es llamada
        bloqueante (supabase-py es síncrona) — quien la use desde la UI debe
        mandarla a un hilo aparte (asyncio.to_thread) para no congelar la
        ventana, igual que hace sesion_view.py con el login.
        """
        respuesta = (
            client.from_("platillos")
            .select(_COLUMNAS)
            .order("orden")
            .order("id")
            .execute()
        )
        return respuesta.data or []

    @staticmethod
    def _siguiente_orden() -> int:
        """El siguiente valor de `orden` para que un platillo nuevo caiga al
        FINAL de la lista. `orden` tiene default 0 en la tabla, así que si no
        se manda algo explícito todos los platillos nuevos se irían hasta
        arriba — por eso crear() siempre calcula esto primero.

        Solo trae la columna `orden` (nunca select('*')) del último registro
        por orden descendente; si la tabla está vacía, arranca en 1."""
        respuesta = (
            client.from_("platillos")
            .select("orden")
            .order("orden", desc=True)
            .limit(1)
            .execute()
        )
        filas = respuesta.data or []
        if not filas:
            return 1
        return int(filas[0]["orden"] or 0) + 1

    @staticmethod
    def crear(datos: dict) -> dict:
        """Inserta un platillo nuevo. `datos` trae nombre/descripcion/
        categoria/precio ya validados por la vista (categoría dentro de las
        3 fijas, precio numérico no-negativo — los CHECK de la tabla son el
        respaldo final, pero validar antes en el formulario evita que el
        usuario vea un error crudo de Postgres).

        No manda `image_url` — ese campo no existe en el formulario todavía
        (Fase 3, Cloudflare); se queda NULL y la fila cae al placeholder
        assets/taco.jpg, igual que las 10 filas de prueba. Sí manda `orden`,
        calculado aquí, para que el platillo quede al final de la lista.
        """
        fila = {
            "nombre": datos["nombre"],
            "descripcion": datos.get("descripcion") or None,
            "categoria": datos["categoria"],
            "precio": datos["precio"],
            "orden": PlatilloDAO._siguiente_orden(),
        }
        respuesta = client.from_("platillos").insert(fila).execute()
        if not respuesta.data:
            # No debería pasar (un INSERT bloqueado por RLS sí lanza error de
            # Postgres, a diferencia de UPDATE/DELETE) pero se cubre por
            # consistencia con actualizar()/cambiar_visibilidad() y por si
            # algún día cambian las políticas.
            raise EscrituraSinEfecto("El insert no devolvió ninguna fila.")
        return respuesta.data[0]

    @staticmethod
    def actualizar(id_platillo: int, datos: dict) -> dict:
        """Actualiza nombre/descripcion/categoria/precio de un platillo
        existente. No toca `visible`, `image_url` ni `orden` — eso lo maneja
        cambiar_visibilidad() y la futura Fase 3 por separado."""
        fila = {
            "nombre": datos["nombre"],
            "descripcion": datos.get("descripcion") or None,
            "categoria": datos["categoria"],
            "precio": datos["precio"],
        }
        respuesta = (
            client.from_("platillos").update(fila).eq("id", id_platillo).execute()
        )
        if not respuesta.data:
            # RLS bloqueó el UPDATE en silencio (0 filas coincidieron) — ver
            # la nota de EscrituraSinEfecto al inicio del archivo. Sin este
            # chequeo, esto se vería como un guardado exitoso que en
            # realidad no tocó la base.
            raise EscrituraSinEfecto(
                f"El update de platillos id={id_platillo} no afectó ninguna fila."
            )
        return respuesta.data[0]

    @staticmethod
    def eliminar(id_platillo: int) -> None:
        """Borra la fila de verdad — a diferencia de ocultar (visible=false),
        esto no se puede deshacer. La vista es responsable de pedir
        confirmación ANTES de llamar a este método."""
        respuesta = client.from_("platillos").delete().eq("id", id_platillo).execute()
        if not respuesta.data:
            # Mismo caso que actualizar(): un DELETE que RLS bloquea también
            # "tiene éxito" con data=[] en vez de lanzar un error.
            raise EscrituraSinEfecto(
                f"El delete de platillos id={id_platillo} no afectó ninguna fila."
            )

    @staticmethod
    def cambiar_visibilidad(id_platillo: int, visible: bool) -> dict:
        """Solo cambia la columna `visible` — nunca borra la fila. Al ponerla
        en False, el platillo deja de salir en el menú público (RLS de anon
        exige visible = true) pero se queda intacto en Supabase y en la tabla
        del panel, con el badge en rojo diciendo OCULTO."""
        respuesta = (
            client.from_("platillos")
            .update({"visible": visible})
            .eq("id", id_platillo)
            .execute()
        )
        if not respuesta.data:
            # El bug real que se encontró verificando la Fase 2.6 contra
            # Supabase de verdad (ver la nota grande al inicio del archivo):
            # sin este chequeo, el ojito se pintaba en rojo aunque la fila
            # seguía visible=true en la base.
            raise EscrituraSinEfecto(
                f"El cambio de visibilidad de platillos id={id_platillo} no afectó ninguna fila."
            )
        return respuesta.data[0]
