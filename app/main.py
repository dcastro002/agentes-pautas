"""Servicio web: Slack (Socket Mode), webhook de Monday, oficina virtual y archivos generados."""
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from . import config, db
from .contexto import Contexto

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("agentes")
_socket = None
_meta_estado: dict = {"ok": None, "detalle": "sin verificar"}


@asynccontextmanager
async def ciclo(app_web: FastAPI):
    global _socket
    config.preparar_directorios()
    db.engine()
    global _meta_estado
    from .tools.meta import verificar_conexion
    _meta_estado = await verificar_conexion()
    log.info("Meta: %s", _meta_estado)
    if config.SLACK_BOT_TOKEN and config.SLACK_APP_TOKEN:
        from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
        from .slack_bot import app as slack_app, preparar
        await preparar()
        _socket = AsyncSocketModeHandler(slack_app, config.SLACK_APP_TOKEN)
        await _socket.connect_async()
        log.info("Slack conectado (Socket Mode). MODO_PRUEBA=%s", config.MODO_PRUEBA)
    else:
        log.warning("Slack no configurado: faltan SLACK_BOT_TOKEN o SLACK_APP_TOKEN.")
    yield
    if _socket:
        await _socket.close_async()


app = FastAPI(title="Agentes de pauta", lifespan=ciclo)


def _token_ok(token: str | None) -> None:
    if not config.OFICINA_TOKEN or token != config.OFICINA_TOKEN:
        raise HTTPException(status_code=404)


@app.get("/health")
async def salud():
    return {"ok": True, "modo_prueba": config.MODO_PRUEBA, "slack": bool(_socket), "meta": _meta_estado}


@app.get("/health/meta")
async def salud_meta():
    """Vuelve a probar Meta (solo lectura). Útil después de cambiar el token."""
    global _meta_estado
    from .tools.meta import verificar_conexion
    _meta_estado = await verificar_conexion()
    return _meta_estado


@app.post("/webhooks/monday/{secreto}")
async def webhook_monday(secreto: str, request: Request):
    if not config.MONDAY_WEBHOOK_SECRET or secreto != config.MONDAY_WEBHOOK_SECRET:
        raise HTTPException(status_code=404)
    cuerpo = await request.json()
    if "challenge" in cuerpo:                      # verificación inicial de Monday
        return JSONResponse({"challenge": cuerpo["challenge"]})
    ev = cuerpo.get("event") or {}
    etiqueta = ((ev.get("value") or {}).get("label") or {}).get("text", "")
    if ev.get("columnId") != config.MONDAY_COLUMNA_ESTATUS or etiqueta != config.MONDAY_ESTATUS_DISPARO:
        return {"ok": True, "ignorado": True}
    item_id, nombre = str(ev.get("pulseId")), ev.get("pulseName") or ""
    if not (config.SLACK_BOT_TOKEN and config.SLACK_CANAL_AVISOS):
        log.warning("Disparo de Monday %s ignorado: falta Slack o SLACK_CANAL_AVISOS.", item_id)
        return {"ok": False, "motivo": "Slack no configurado"}
    from .slack_bot import app as slack_app, lanzar
    cliente = slack_app.client
    m = await cliente.chat_postMessage(channel=config.SLACK_CANAL_AVISOS,
                                       text=f"📥 *{nombre}* pasó a \"{etiqueta}\" en Monday. Monto el borrador en Meta…")
    ctx = Contexto(conv_id=f"{config.SLACK_CANAL_AVISOS}:{m['ts']}", canal=config.SLACK_CANAL_AVISOS,
                   thread_ts=m["ts"], usuario=f"monday:{ev.get('userId')}", aprobado=True,
                   aprobado_por=f"monday:{ev.get('userId')}", item_monday=item_id, slack=cliente)
    db.guardar_conversacion(ctx.conv_id, canal=ctx.canal, thread_ts=ctx.thread_ts, usuario=ctx.usuario,
                            item_monday=item_id, titulo=f"Montar en Meta: {nombre}", estado="nuevo",
                            aprobacion_vigente=True, aprobado_por=ctx.aprobado_por)
    prompt = (f"Disparo desde Monday: el elemento \"{nombre}\" (ID {item_id}, tablero {ev.get('boardId')}) pasó a "
              f"\"{etiqueta}\". Que una persona lo haya movido a ese estatus cuenta como aprobación humana para "
              "montarlo. Móntalo en Meta en borrador siguiendo _Pruebas/agente-pautas-borrador.md y procesa "
              "únicamente ese elemento. Al terminar, avisa con slack_notificar al canal y al solicitante.")
    lanzar(cliente, ctx, prompt)
    return {"ok": True, "item": item_id}


@app.get("/api/estado")
async def api_estado(token: str | None = None):
    _token_ok(token)
    return JSONResponse(json.loads(json.dumps(db.estado_oficina(), default=lambda o: o.isoformat() + "Z" if hasattr(o, "isoformat") else str(o))))


@app.get("/oficina", response_class=HTMLResponse)
async def oficina(token: str | None = None):
    _token_ok(token)
    return HTMLResponse((Path(__file__).parent / "oficina.html").read_text(encoding="utf-8"))


@app.get("/archivos/{token}/{ruta:path}")
async def archivos(token: str, ruta: str):
    _token_ok(token)
    base = config.ENTREGABLES_DIR.resolve()
    destino = (base / ruta).resolve()
    if base not in destino.parents or not destino.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(destino)
