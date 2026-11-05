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
_google_estado: dict = {"ok": None, "detalle": "sin verificar"}
_linkedin_estado: dict = {"ok": None, "detalle": "sin verificar"}


@asynccontextmanager
async def ciclo(app_web: FastAPI):
    global _socket
    config.preparar_directorios()
    db.engine()
    global _meta_estado
    from .tools.meta import verificar_conexion
    _meta_estado = await verificar_conexion()
    log.info("Meta: %s", _meta_estado)
    global _google_estado
    from .tools.google_ads import verificar_conexion as verificar_google
    _google_estado = await verificar_google()
    log.info("Google Ads: %s", _google_estado)
    global _linkedin_estado
    from .tools.linkedin import verificar_conexion as verificar_linkedin
    _linkedin_estado = await verificar_linkedin()
    log.info("LinkedIn: %s", _linkedin_estado)
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
    return {"ok": True, "modo_prueba": config.MODO_PRUEBA, "slack": bool(_socket), "meta": _meta_estado,
            "google_ads": _google_estado, "linkedin": _linkedin_estado}


@app.get("/health/meta")
async def salud_meta():
    """Vuelve a probar Meta (solo lectura). Útil después de cambiar el token."""
    global _meta_estado
    from .tools.meta import verificar_conexion
    _meta_estado = await verificar_conexion()
    return _meta_estado


@app.get("/health/google-ads")
async def salud_google():
    """Vuelve a probar Google Ads (solo lectura). Útil después de cambiar credenciales."""
    global _google_estado
    from .tools.google_ads import verificar_conexion as verificar_google
    _google_estado = await verificar_google()
    return _google_estado


@app.get("/health/linkedin")
async def salud_linkedin():
    """Vuelve a probar LinkedIn (solo lectura). Útil después de cambiar el token."""
    global _linkedin_estado
    from .tools.linkedin import verificar_conexion as verificar_linkedin
    _linkedin_estado = await verificar_linkedin()
    return _linkedin_estado


@app.post("/webhooks/monday/{secreto}")
async def webhook_monday(secreto: str, request: Request):
    if not config.MONDAY_WEBHOOK_SECRET or secreto != config.MONDAY_WEBHOOK_SECRET:
        raise HTTPException(status_code=404)
    cuerpo = await request.json()
    if "challenge" in cuerpo:                      # verificación inicial de Monday
        return JSONResponse({"challenge": cuerpo["challenge"]})
    ev = cuerpo.get("event") or {}
    from . import avisos
    if avisos.ya_visto(ev):
        return {"ok": True, "ignorado": "repetido"}
    if ev.get("boardId") and config.MONDAY_TABLEROS_PERMITIDOS and str(ev["boardId"]) not in config.MONDAY_TABLEROS_PERMITIDOS:
        return {"ok": True, "ignorado": "tablero no permitido"}
    etiqueta = ((ev.get("value") or {}).get("label") or {}).get("text", "")
    es_nuevo = ev.get("type") == "create_pulse"
    if es_nuevo and not config.AVISAR_ELEMENTO_NUEVO:
        return {"ok": True, "ignorado": "avisos de elemento nuevo apagados"}
    if not es_nuevo and ev.get("columnId") != config.MONDAY_COLUMNA_ESTATUS:
        return {"ok": True, "ignorado": True}
    if not (config.SLACK_BOT_TOKEN and config.SLACK_CANAL_AVISOS):
        log.warning("Evento de Monday ignorado: falta Slack o SLACK_CANAL_AVISOS.")
        return {"ok": False, "motivo": "Slack no configurado"}
    from .slack_bot import app as slack_app, lanzar
    cliente = slack_app.client

    # 1) Elemento nuevo creado a mano → aviso a la responsable
    if es_nuevo:
        try:
            return {"ok": True, **(await avisos.avisar_nuevo(cliente, ev))}
        except Exception as e:  # noqa: BLE001
            log.exception("Aviso de elemento nuevo falló")
            return {"ok": False, "motivo": str(e)[:200]}

    # 2) Quedó en Error / Falta info → DM a quien lo creó y al Solicitante
    if etiqueta.lower() in {e.lower() for e in config.MONDAY_ESTATUS_AVISO}:
        try:
            return {"ok": True, **(await avisos.avisar_problema(cliente, str(ev.get("pulseId")), etiqueta))}
        except Exception as e:  # noqa: BLE001
            log.exception("Aviso de problema falló")
            return {"ok": False, "motivo": str(e)[:200]}

    # 3) Pasó a "Listo para montar" → el agente lo monta en Meta en pausa
    if etiqueta != config.MONDAY_ESTATUS_DISPARO:
        return {"ok": True, "ignorado": True}
    item_id, nombre = str(ev.get("pulseId")), ev.get("pulseName") or ""
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
              "únicamente ese elemento. Al terminar, avisa con slack_notificar al canal y al responsable. "
              "Si queda en \"Error\" o \"Falta info\", explica el motivo en las Notas del agente: el servidor "
              "le avisa solo por DM a quien creó el elemento y a su Solicitante con esas notas.")
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
