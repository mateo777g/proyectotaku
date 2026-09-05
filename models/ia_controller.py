"""
models/ia_controller.py
El agente de IA del panel (Fase 6) — views/agenteIA_view.py es la única
pantalla que lo usa.

Patrón copiado de EJEMPLOS/ia_controller.py: se leen datos reales del
negocio con un DAO, se aplanan a texto, se meten al system prompt, se llama
al modelo. La diferencia con el ejemplo es que aquí SÍ hay varias tablas
reales que contar — Fase 5 (sistema de mesas) ya dejó ventas/venta_items
con datos de verdad, así que este archivo junta 4 tablas (platillos, mesas,
ventas, venta_items) en vez de una sola, y no hay ninguna simulación de
red neuronal/Keras de adorno como en el ejemplo — el ejemplo la traía
apagada de todos modos.

MODELO: OpenAI (gpt-4o por defecto, configurable con OPENAI_MODEL en el
.env), NO Claude/el SDK `anthropic`. El roadmap (CLAUDE.md y el .txt)
decía "aquí se usa Claude, salvo que el dueño diga lo contrario" — el
dueño puso OPENAI_API_KEY en el .env él mismo para esta fase (2026-09-05),
así que esa es la decisión que queda y por eso este archivo usa el SDK
`openai`, no `anthropic`.

Igual que platillo_dao.py/mesa_dao.py: los métodos de aquí son bloqueantes
(el cliente de OpenAI, igual que supabase-py, es síncrono) — quien llame
desde la UI debe mandarlo a un hilo aparte (asyncio.to_thread), igual que
ya hace agenteIA_view.py para todo lo demás. No hay caché de ningún tipo:
cada pregunta vuelve a leer las 4 tablas completas, mismo criterio de
"nada de caché escondida en el panel" que ya sigue el resto del proyecto
(ver la nota de auditoría de borrado en platillo_dao.py) — el precio es
una llamada más a Supabase por pregunta, que a esta escala no cuesta nada.
"""
import datetime
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from models.mesa_dao import MesaDAO
from models.platillo_dao import PlatilloDAO
from models.venta_dao import VentaDAO

# .env vive en la raíz del repo, un nivel arriba de esta carpeta — mismo
# mecanismo que supabase_client.py.
_RUTA_ENV = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_RUTA_ENV)

_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# Configurable por si algún día se quiere probar otro modelo sin tocar
# código — pero con un default sensato, igual que ADMIN_EMAIL en
# supabase_client.py trae su propio default vacío.
_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")


def _hora_local(valor: str | None) -> str:
    """Convierte el timestamp UTC que regresa Supabase a hora LOCAL de la
    máquina antes de metérselo al modelo — mismo criterio que
    _tiempo_relativo() en home_view.py: si se le pasara el UTC crudo, el
    agente podría contestar "ayer" o "hoy" mal para preguntas del tipo
    "¿cuánto vendí hoy?". Formato simple y legible, no hace falta el
    "hace N horas" relativo de home_view porque aquí el propio modelo hace
    esa cuenta a partir de la fecha/hora actual que se le da en el prompt
    (ver HOY_TEXTO abajo)."""
    if not valor:
        return "—"
    try:
        fecha = datetime.datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return "—"
    return fecha.astimezone().strftime("%Y-%m-%d %H:%M")


def _formatear_platillos(platillos: list[dict]) -> str:
    if not platillos:
        return "No hay platillos registrados en el menú."
    lineas = []
    for p in platillos:
        estado = "visible" if p.get("visible") else "OCULTO (no sale en el menú público)"
        descripcion = f" — {p['descripcion']}" if p.get("descripcion") else ""
        lineas.append(
            f"- #{p['id']} {p['nombre']} ({p['categoria']}) — ${p['precio']} — "
            f"{estado}{descripcion}"
        )
    return "\n".join(lineas)


def _formatear_mesas(mesas: list[dict]) -> str:
    if not mesas:
        return "No hay mesas registradas en el catálogo."
    return "\n".join(f"- {m['nombre']}" for m in mesas)


def _formatear_ventas(ventas: list[dict]) -> str:
    if not ventas:
        return "Todavía no hay ninguna venta registrada."
    lineas = []
    for v in ventas:
        cierre = f" — cerrada el {_hora_local(v['cerrada_at'])}" if v.get("cerrada_at") else ""
        lineas.append(
            f"- Venta #{v['id']} — {v['mesa']} — {v['estado']} — "
            f"total ${v['total']} — abierta el {_hora_local(v['created_at'])}{cierre}"
        )
        for item in v.get("items", []):
            lineas.append(
                f"    · {item['cantidad']} x {item['nombre']} "
                f"(${item['precio_unitario']} c/u)"
            )
    return "\n".join(lineas)


class IAController:
    def __init__(self):
        if not _OPENAI_API_KEY:
            raise RuntimeError(
                "Falta OPENAI_API_KEY en el .env — el agente de IA no puede "
                "arrancar sin ella."
            )
        self.client = OpenAI(api_key=_OPENAI_API_KEY)

    def preguntar(self, pregunta_usuario: str, historial: list[dict] | None = None) -> str:
        """Bloqueante — llamar siempre desde asyncio.to_thread(), igual que
        el resto de las llamadas a Supabase/Cloudflare en este proyecto.

        `historial` (opcional) es la conversación previa de esta sesión de
        chat, como lista de {"role": "user"|"assistant", "content": str} en
        el mismo orden en que se dijeron — así el agente recuerda lo que ya
        se habló (p. ej. "¿y cuánto fue de eso en propinas?" después de una
        pregunta sobre ventas). agenteIA_view.py es quien la arma y la va
        creciendo; este método no persiste nada por su cuenta."""
        platillos = PlatilloDAO.obtener_todos()
        mesas = MesaDAO.obtener_todos()
        ventas = VentaDAO.obtener_ventas_con_items()

        ahora = datetime.datetime.now().astimezone()
        dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

        system_prompt = (
            "Eres el asistente de datos de Taku Monky, una taquería. Ayudas "
            "al dueño del negocio a entender su menú, sus mesas y sus "
            "ventas de forma clara, profesional y amigable, en español.\n\n"
            f"HOY ES: {dias[ahora.weekday()]} {ahora.strftime('%Y-%m-%d %H:%M')} "
            "(hora local del negocio) — úsalo para calcular \"hoy\", \"ayer\", "
            "\"esta semana\", etc. cuando te pregunten sobre fechas.\n\n"
            "Si te preguntan algo que no tiene que ver con el negocio (el "
            "menú, las mesas o las ventas), redirige amablemente diciendo "
            "que solo manejas los datos de Taku Monky.\n\n"
            "MENÚ ACTUAL (tabla platillos):\n"
            f"{_formatear_platillos(platillos)}\n\n"
            "MESAS DEL NEGOCIO (tabla mesas):\n"
            f"{_formatear_mesas(mesas)}\n\n"
            "VENTAS CON SUS PRODUCTOS (tablas ventas + venta_items, más "
            "recientes primero; 'abierta' es una cuenta que sigue en curso "
            "en una mesa, 'cerrada' ya se cobró):\n"
            f"{_formatear_ventas(ventas)}\n\n"
            "Usa estos datos exactos para responder — no inventes "
            "platillos, precios, mesas ni ventas que no estén en esta "
            "lista, y no redondees ni resumas de más si te piden un número "
            "preciso. Si algo no se puede calcular con estos datos (por "
            "ejemplo, algo que necesitaría una tabla que no tienes), dilo "
            "claramente en vez de adivinar. No puedes modificar nada del "
            "sistema — si te piden abrir/cerrar una venta o cambiar el "
            "menú, explica que eso se hace desde el panel o mesas.html, "
            "tú solo consultas."
        )

        mensajes = [{"role": "system", "content": system_prompt}]
        mensajes.extend(historial or [])
        mensajes.append({"role": "user", "content": pregunta_usuario})

        respuesta = self.client.chat.completions.create(
            model=_OPENAI_MODEL,
            messages=mensajes,
            temperature=0.4,
        )
        return respuesta.choices[0].message.content
