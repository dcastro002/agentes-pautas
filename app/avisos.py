"""Avisos automáticos por eventos de Monday, sin pasar por el agente (no gastan tokens).

- Elemento nuevo creado a mano en el tablero → aviso al responsable (Majo) en el canal y por DM.
- Estatus del agente cambia a "Error" o "Falta info" → DM a quien creó el elemento y a su Solicitante,
  con lo que dicen las Notas del agente, y aviso en el canal.
"""
import json
import logging

from . import config
from .tools import monday
from .tools.slack import id_por_correo

log = logging.getLogger("agentes")
_vistos: set[str] = set()      # triggerUuid ya procesados (Monday reintenta webhooks)
_usuario_servicio: str | None = None


def ya_visto(evento: dict) -> bool:
    clave = evento.get("triggerUuid") or ""
    if not clave:
        return False
    if clave in _vistos:
        return True
    _vistos.add(clave)
    if len(_vistos) > 5000:
        _vistos.clear()
    return False


async def usuario_servicio() -> str | None:
    """ID del usuario de Monday dueño del token: lo que crea el agente no se avisa como 'creado a mano'."""
    global _usuario_servicio
    if _usuario_servicio is None:
        try:
            _usuario_servicio = str((await monday.gql("query { me { id } }"))["me"]["id"])
        except Exception as e:  # noqa: BLE001
            log.warning("No pude leer el usuario de Monday del token: %s", e)
            _usuario_servicio = ""
    return _usuario_servicio or None


async def datos_item(item_id: str) -> dict | None:
    columnas = [config.MONDAY_COLUMNA_SOLICITANTE, config.MONDAY_COLUMNA_NOTAS, config.MONDAY_COLUMNA_ESTATUS]
    d = await monday.gql("""query ($i:[ID!], $c:[String!]) { items(ids:$i) { id name url board { id }
        creator { id name email } column_values(ids:$c) { id text value } } }""",
                         {"i": [str(item_id)], "c": columnas})
    items = d.get("items") or []
    return items[0] if items else None


async def correos_de(item: dict) -> list[str]:
    """Solicitante(s) del elemento + quien lo creó, sin repetir."""
    correos: list[str] = []
    for cv in item.get("column_values", []):
        if cv["id"] == config.MONDAY_COLUMNA_SOLICITANTE and cv.get("value"):
            personas = json.loads(cv["value"]).get("personsAndTeams", [])
            ids = [str(p["id"]) for p in personas if p.get("kind") == "person"]
            if ids:
                u = await monday.gql("query ($u:[ID!]) { users(ids:$u) { email } }", {"u": ids})
                correos += [x["email"] for x in u.get("users", []) if x.get("email")]
    creador = (item.get("creator") or {})
    if creador.get("email") and str(creador.get("id")) != (await usuario_servicio() or ""):
        correos.append(creador["email"])
    vistos, unicos = set(), []
    for c in correos:
        if c.lower() not in vistos:
            vistos.add(c.lower())
            unicos.append(c)
    return unicos


def _texto(item: dict, columna: str) -> str:
    return next((cv.get("text") or "" for cv in item.get("column_values", []) if cv["id"] == columna), "")


async def _dm(cliente, correo: str, texto: str) -> bool:
    uid = await id_por_correo(cliente, correo)
    if not uid:
        log.warning("No encontré en Slack a %s", correo)
        return False
    await cliente.chat_postMessage(channel=uid, text=texto)
    return True


async def avisar_nuevo(cliente, evento: dict) -> dict:
    """Alguien creó un elemento a mano en el tablero → aviso a la responsable."""
    item_id = str(evento.get("pulseId"))
    if str(evento.get("userId")) == (await usuario_servicio() or "-"):
        return {"ignorado": "lo creó el agente"}
    item = await datos_item(item_id)
    if not item:
        return {"ignorado": "elemento no encontrado"}
    creador = (item.get("creator") or {}).get("name") or "alguien"
    texto = (f"📝 *Nueva solicitud en Monday:* <{item['url']}|{item['name']}>\n"
             f"La creó {creador}. Revísala y, cuando esté completa, pásala a \"{config.MONDAY_ESTATUS_DISPARO}\" "
             "para que el agente la monte en Meta (en pausa).")
    enviados = []
    resp_id = await id_por_correo(cliente, config.SLACK_RESPONSABLE_EMAIL) if config.SLACK_RESPONSABLE_EMAIL else None
    if config.SLACK_CANAL_AVISOS:
        prefijo = f"<@{resp_id}> " if resp_id else ""
        await cliente.chat_postMessage(channel=config.SLACK_CANAL_AVISOS, text=prefijo + texto)
        enviados.append("canal")
    if resp_id:
        await cliente.chat_postMessage(channel=resp_id, text=texto)
        enviados.append("responsable")
    return {"item": item_id, "enviados": enviados}


async def avisar_problema(cliente, item_id: str, etiqueta: str, detalle: str | None = None) -> dict:
    """El elemento quedó en Error o Falta info → DM a quien lo creó y a su Solicitante con el motivo."""
    item = await datos_item(item_id)
    if not item:
        return {"ignorado": "elemento no encontrado"}
    notas = (detalle or _texto(item, config.MONDAY_COLUMNA_NOTAS)).strip()
    if len(notas) > 1500:
        notas = "…" + notas[-1500:]   # lo más reciente está al final
    icono = "⚠️" if etiqueta.lower() == "error" else "✋"
    texto = (f"{icono} *<{item['url']}|{item['name']}>* quedó en *{etiqueta}*.\n"
             + (f"*Qué pasó / qué falta:*\n>{notas.replace(chr(10), chr(10) + '>')}\n" if notas else "")
             + "Corrígelo en el elemento y vuelve a pasarlo a "
             f"\"{config.MONDAY_ESTATUS_DISPARO}\", o escríbele al bot en Slack si tienes dudas.")
    enviados = []
    for correo in await correos_de(item):
        if await _dm(cliente, correo, texto):
            enviados.append(correo)
    if config.SLACK_CANAL_AVISOS:
        quienes = ", ".join(enviados) if enviados else "nadie (el elemento no tiene Solicitante ni creador en Slack)"
        await cliente.chat_postMessage(channel=config.SLACK_CANAL_AVISOS, text=f"{texto}\n_Avisado: {quienes}_")
    return {"item": item_id, "enviados": enviados}
