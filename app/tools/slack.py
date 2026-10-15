"""Herramienta de avisos por Slack: canal del equipo, solicitante del elemento de Monday y responsable."""
from claude_agent_sdk import create_sdk_mcp_server, tool

from .. import config, db
from ..contexto import Contexto
from . import monday
from .comun import error, esquema, ok


async def id_por_correo(cliente, correo: str) -> str | None:
    try:
        r = await cliente.users_lookupByEmail(email=correo)
        return r["user"]["id"]
    except Exception:
        return None


def crear_servidor(ctx: Contexto):
    @tool("slack_notificar",
          "Avisa por Slack. Destinatarios: 'canal' (canal de avisos del equipo), 'solicitante' (DM a quien figura "
          "como Solicitante en el elemento de Monday; requiere item_id) y 'responsable' (DM a quien aprueba, y "
          "mención en el canal). Úsalo al terminar un flujo que toca Monday o Meta, y siempre que haya 'Falta info' o "
          "'Error', explicando exactamente qué falta o qué falló y cómo corregirlo.",
          esquema({"mensaje": {"type": "string"},
                   "destinatarios": {"type": "array", "items": {"type": "string",
                                                                "enum": ["canal", "solicitante", "responsable"]}},
                   "item_id": {"type": "string"}}, ["mensaje", "destinatarios"]))
    async def slack_notificar(a):
        if ctx.slack is None:
            return ok({"simulado": True, "nota": "Slack no está conectado en este entorno.", "mensaje": a["mensaje"]})
        enviados, faltantes = [], []
        destinos = set(a.get("destinatarios") or [])
        resp_id = await id_por_correo(ctx.slack, config.SLACK_RESPONSABLE_EMAIL) if config.SLACK_RESPONSABLE_EMAIL else None
        texto = a["mensaje"]
        try:
            if "canal" in destinos:
                if config.SLACK_CANAL_AVISOS:
                    prefijo = f"<@{resp_id}> " if ("responsable" in destinos and resp_id) else ""
                    await ctx.slack.chat_postMessage(channel=config.SLACK_CANAL_AVISOS, text=prefijo + texto)
                    enviados.append("canal")
                else:
                    faltantes.append("canal (falta SLACK_CANAL_AVISOS)")
            if "responsable" in destinos:
                if resp_id:
                    await ctx.slack.chat_postMessage(channel=resp_id, text=texto)
                    enviados.append("responsable")
                else:
                    faltantes.append("responsable (falta SLACK_RESPONSABLE_EMAIL o no está en Slack)")
            if "solicitante" in destinos:
                item = a.get("item_id") or ctx.item_monday
                correos = await monday.correos_solicitantes(item, config.MONDAY_COLUMNA_SOLICITANTE) if item else []
                if not correos:
                    faltantes.append("solicitante (el elemento no tiene Solicitante)")
                for correo in correos:
                    uid = await id_por_correo(ctx.slack, correo)
                    if uid:
                        await ctx.slack.chat_postMessage(channel=uid, text=texto)
                        enviados.append(f"solicitante {correo}")
                    else:
                        faltantes.append(f"solicitante {correo} (no encontrado en Slack)")
            db.evento(ctx.conv_id, "avisos", "slack", f"{', '.join(enviados) or 'nadie'}: {texto[:300]}")
            return ok({"enviados": enviados, "no_enviados": faltantes})
        except Exception as e:
            return error(f"ERROR DE SLACK: {e}")

    return create_sdk_mcp_server(name="slack", version="1.0.0", tools=[slack_notificar]), [slack_notificar]
