"""Bot de Slack: recibe pedidos, muestra resultados y botones de aprobación, y continúa la conversación."""
import asyncio
import datetime as dt
import re
import time

import httpx
from slack_bolt.async_app import AsyncApp

from . import config, db, runner
from .contexto import Contexto

app = AsyncApp(token=config.SLACK_BOT_TOKEN or "xoxb-sin-configurar")
_tareas: set[asyncio.Task] = set()
_bot_user_id: str | None = None
LIMITE = 2900


# ---------------------------------------------------------------- formato
def a_mrkdwn(texto: str) -> str:
    """Markdown → formato de Slack."""
    lineas, salida, en_tabla = texto.splitlines(), [], False
    for linea in lineas:
        es_tabla = linea.strip().startswith("|")
        if es_tabla and not en_tabla:
            salida.append("```")
            en_tabla = True
        if not es_tabla and en_tabla:
            salida.append("```")
            en_tabla = False
        if not es_tabla:
            linea = re.sub(r"^#{1,6}\s+(.*)$", r"*\1*", linea)
            linea = re.sub(r"\*\*(.+?)\*\*", r"*\1*", linea)
            linea = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"<\2|\1>", linea)
        salida.append(linea)
    if en_tabla:
        salida.append("```")
    return "\n".join(salida)


def trozos(texto: str, limite: int = LIMITE) -> list[str]:
    partes, actual = [], ""
    for parrafo in texto.split("\n\n"):
        candidato = (actual + "\n\n" + parrafo) if actual else parrafo
        if len(candidato) <= limite:
            actual = candidato
            continue
        if actual:
            partes.append(actual)
        while len(parrafo) > limite:
            partes.append(parrafo[:limite])
            parrafo = parrafo[limite:]
        actual = parrafo
    if actual:
        partes.append(actual)
    return partes or ["(sin texto)"]


def link_archivo(ruta: str) -> str:
    if not (config.PUBLIC_URL and config.OFICINA_TOKEN):
        return f"`{ruta}`"
    relativa = ruta.split("_Entregables/", 1)[-1]
    return f"<{config.PUBLIC_URL}/archivos/{config.OFICINA_TOKEN}/{relativa}|{relativa.rsplit('/', 1)[-1]}>"


def botones(conv_id: str) -> dict:
    return {"type": "actions", "block_id": "aprobacion", "elements": [
        {"type": "button", "style": "primary", "action_id": "aprobar", "value": conv_id,
         "text": {"type": "plain_text", "text": "Aprobar"}},
        {"type": "button", "action_id": "cambios", "value": conv_id,
         "text": {"type": "plain_text", "text": "Pedir cambios"}},
    ]}


# ---------------------------------------------------------------- ejecución
async def correr(cliente, ctx: Contexto, prompt: str) -> None:
    inicio = time.monotonic()
    aviso = await cliente.chat_postMessage(channel=ctx.canal, thread_ts=ctx.thread_ts,
                                           text="⏳ Trabajando en esto…")
    res = await runner.ejecutar(ctx, prompt)
    minutos = (time.monotonic() - inicio) / 60
    if res.error and not res.texto:
        await cliente.chat_update(channel=ctx.canal, ts=aviso["ts"],
                                  text=f"⚠️ Algo falló: {res.error[:500]}\nEscríbeme en este hilo para reintentar.")
        return
    cuerpo = a_mrkdwn(res.texto)
    if res.archivos:
        cuerpo += "\n\n*Archivos:* " + " · ".join(link_archivo(a) for a in res.archivos)
    if res.error:
        cuerpo += f"\n\n⚠️ {res.error}"
    partes = trozos(cuerpo)
    for i, parte in enumerate(partes):
        ultimo = i == len(partes) - 1
        bloques = [{"type": "section", "text": {"type": "mrkdwn", "text": parte}}]
        if ultimo and res.pide_aprobacion:
            bloques.append(botones(ctx.conv_id))
        await cliente.chat_postMessage(channel=ctx.canal, thread_ts=ctx.thread_ts, text=parte[:3000], blocks=bloques)
    pie = f"✅ Listo · {minutos:.1f} min · costo estimado ${res.costo_usd:.2f} USD"
    if config.MODO_PRUEBA:
        pie += " · MODO PRUEBA (nada se escribió en Meta)"
    await cliente.chat_update(channel=ctx.canal, ts=aviso["ts"], text=pie)


def lanzar(cliente, ctx: Contexto, prompt: str) -> None:
    tarea = asyncio.create_task(correr(cliente, ctx, prompt))
    _tareas.add(tarea)
    tarea.add_done_callback(_tareas.discard)


async def descargar_archivos(evento: dict, conv_id: str) -> list[str]:
    rutas = []
    carpeta = config.ENTREGABLES_DIR / "slack" / re.sub(r"[^\w]+", "_", conv_id)
    for f in evento.get("files", []) or []:
        url = f.get("url_private_download") or f.get("url_private")
        if not url:
            continue
        carpeta.mkdir(parents=True, exist_ok=True)
        nombre = re.sub(r"[^\w.\-]+", "_", f.get("name") or f.get("id"))
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as cli:
            r = await cli.get(url, headers={"Authorization": f"Bearer {config.SLACK_BOT_TOKEN}"})
        if r.status_code == 200:
            (carpeta / nombre).write_bytes(r.content)
            rutas.append(f"_Entregables/slack/{carpeta.name}/{nombre}")
    return rutas


async def atender(evento: dict, cliente, texto: str) -> None:
    canal = evento["channel"]
    hilo = evento.get("thread_ts") or evento["ts"]
    conv_id = f"{canal}:{hilo}"
    conv = db.obtener_conversacion(conv_id)
    usuario = evento.get("user", "")
    archivos = await descargar_archivos(evento, conv_id)
    adjuntos = ("\n\nArchivos adjuntos en Slack (ya guardados en el proyecto):\n" + "\n".join(f"- {a}" for a in archivos)) if archivos else ""
    if conv and conv.get("estado") == "trabajando":
        await cliente.chat_postMessage(channel=canal, thread_ts=hilo,
                                       text="Sigo trabajando en el paso anterior; te leo en cuanto termine.")
    encabezado = "Respuesta" if conv else "Pedido nuevo"
    prompt = f"{encabezado} de <@{usuario}> por Slack:\n{texto.strip()}{adjuntos}"
    ctx = Contexto(conv_id=conv_id, canal=canal, thread_ts=hilo, usuario=usuario, slack=cliente,
                   item_monday=(conv or {}).get("item_monday") or "")
    lanzar(cliente, ctx, prompt)


# ---------------------------------------------------------------- eventos
@app.event("app_mention")
async def al_mencionar(event, client):
    texto = re.sub(r"<@[A-Z0-9]+>", "", event.get("text", ""))
    await atender(event, client, texto)


@app.event("message")
async def al_mensaje(event, client):
    if event.get("bot_id") or event.get("subtype") not in (None, "file_share"):
        return
    texto = event.get("text", "") or ""
    if _bot_user_id and f"<@{_bot_user_id}>" in texto:
        return  # lo atiende app_mention
    if event.get("channel_type") == "im":
        await atender(event, client, texto)
        return
    hilo = event.get("thread_ts")
    if hilo and db.obtener_conversacion(f"{event['channel']}:{hilo}"):
        await atender(event, client, texto)


async def _puede_aprobar(usuario: str) -> bool:
    return not config.SLACK_APROBADORES or usuario in config.SLACK_APROBADORES


@app.action("aprobar")
async def al_aprobar(ack, body, client):
    await ack()
    usuario = body["user"]["id"]
    conv_id = body["actions"][0]["value"]
    canal = body["channel"]["id"]
    if not await _puede_aprobar(usuario):
        await client.chat_postEphemeral(channel=canal, user=usuario,
                                        text="Solo las personas autorizadas pueden aprobar este paso.")
        return
    conv = db.obtener_conversacion(conv_id)
    if not conv or conv.get("estado") != "esperando_aprobacion":
        await client.chat_postEphemeral(channel=canal, user=usuario, text="Esta aprobación ya no está vigente.")
        return
    mensaje = body["message"]
    bloques = [b for b in mensaje.get("blocks", []) if b.get("type") != "actions"]
    bloques.append({"type": "context", "elements": [{"type": "mrkdwn", "text": f"✅ Aprobado por <@{usuario}>"}]})
    await client.chat_update(channel=canal, ts=mensaje["ts"], blocks=bloques, text=mensaje.get("text", ""))
    fecha = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    db.guardar_conversacion(conv_id, aprobacion_vigente=True, aprobado_por=usuario)
    db.evento(conv_id, "persona", "aprobó", usuario)
    ctx = Contexto(conv_id=conv_id, canal=conv["canal"], thread_ts=conv["thread_ts"], usuario=conv["usuario"],
                   aprobado=True, aprobado_por=usuario, item_monday=conv.get("item_monday") or "", slack=client)
    lanzar(client, ctx, f"Apruebo. (Aprobado por <@{usuario}> el {fecha} desde Slack.)")


@app.action("cambios")
async def al_pedir_cambios(ack, body, client):
    await ack()
    await client.views_open(trigger_id=body["trigger_id"], view={
        "type": "modal", "callback_id": "cambios_modal",
        "private_metadata": f"{body['actions'][0]['value']}|{body['message']['ts']}",
        "title": {"type": "plain_text", "text": "Pedir cambios"},
        "submit": {"type": "plain_text", "text": "Enviar"},
        "blocks": [{"type": "input", "block_id": "b", "label": {"type": "plain_text", "text": "¿Qué hay que cambiar?"},
                    "element": {"type": "plain_text_input", "action_id": "t", "multiline": True}}],
    })


@app.view("cambios_modal")
async def al_enviar_cambios(ack, body, view, client):
    await ack()
    conv_id, ts_mensaje = view["private_metadata"].split("|", 1)
    texto = view["state"]["values"]["b"]["t"]["value"]
    usuario = body["user"]["id"]
    conv = db.obtener_conversacion(conv_id)
    if not conv:
        return
    await client.chat_postMessage(channel=conv["canal"], thread_ts=conv["thread_ts"],
                                  text=f"✏️ <@{usuario}> pidió cambios:\n>{texto}")
    db.evento(conv_id, "persona", "pidió cambios", texto[:300])
    ctx = Contexto(conv_id=conv_id, canal=conv["canal"], thread_ts=conv["thread_ts"], usuario=conv["usuario"],
                   item_monday=conv.get("item_monday") or "", slack=client)
    lanzar(client, ctx, f"Cambios pedidos por <@{usuario}> (no es aprobación):\n{texto}")


# ---------------------------------------------------------------- arranque
async def preparar() -> None:
    global _bot_user_id
    if config.SLACK_BOT_TOKEN:
        r = await app.client.auth_test()
        _bot_user_id = r.get("user_id")
