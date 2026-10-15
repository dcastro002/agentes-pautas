"""Ejecuta el agente (Claude Agent SDK) sobre el proyecto de la agencia y registra todo en la bitácora."""
import asyncio
import re
from dataclasses import dataclass, field
from pathlib import Path

from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, HookMatcher, ResultMessage,
                              SystemMessage, ToolUseBlock, query)

from . import config, db
from .contexto import Contexto
from .tools import meta, monday, slack

MARCA_APROBACION = "[[APROBACION]]"
INSTRUCCIONES = (Path(__file__).parent / "instrucciones_servidor.md").read_text(encoding="utf-8")
RED_PROHIBIDA = re.compile(r"\b(curl|wget|nc|ncat|ssh|scp|telnet|ftp)\b|graph\.facebook|api\.monday|slack\.com"
                           r"|import\s+(requests|httpx|urllib)|from\s+(requests|httpx|urllib)", re.I)
ARCHIVO_ENTREGABLE = re.compile(r"_Entregables/[^\s`'\")\]>]+?\.(?:html|png|jpg|xlsx|md|pdf|json)")

_semaforo = asyncio.Semaphore(config.MAX_CONCURRENCIA)
_candados: dict[str, asyncio.Lock] = {}


@dataclass
class Resultado:
    texto: str
    pide_aprobacion: bool = False
    costo_usd: float = 0.0
    error: str | None = None
    archivos: list[str] = field(default_factory=list)
    escrituras: list[str] = field(default_factory=list)


def _denegar(motivo: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": motivo}}


async def guardia_bash(entrada, tool_use_id, contexto):
    comando = (entrada.get("tool_input") or {}).get("command", "")
    if RED_PROHIBIDA.search(comando):
        return _denegar("Las llamadas de red desde la terminal están bloqueadas. Usa las herramientas meta_*, "
                        "monday_* o slack_notificar.")
    return {}


async def guardia_archivos(entrada, tool_use_id, contexto):
    datos = entrada.get("tool_input") or {}
    ruta = datos.get("file_path") or datos.get("notebook_path") or ""
    if not ruta:
        return {}
    p = Path(ruta)
    p = (config.AGENCIA_DIR / p).resolve() if not p.is_absolute() else p.resolve()
    agencia = config.AGENCIA_DIR.resolve()
    entregables = config.ENTREGABLES_DIR.resolve()
    if entregables == p or entregables in p.parents:
        return {}
    if agencia in p.parents:
        relativa = p.relative_to(agencia).as_posix()
        if relativa.startswith(".claude/") or relativa == "CLAUDE.md":
            return _denegar("No puedes modificar agentes, skills ni CLAUDE.md desde el servidor.")
        return {}
    return _denegar("Solo puedes escribir dentro del proyecto de la agencia.")


def _opciones(ctx: Contexto, session_id: str | None) -> ClaudeAgentOptions:
    meta_srv, _ = meta.crear_servidor(ctx)
    monday_srv, _ = monday.crear_servidor(ctx)
    slack_srv, _ = slack.crear_servidor(ctx)
    return ClaudeAgentOptions(
        cwd=str(config.AGENCIA_DIR),
        # _Entregables es un enlace al volumen (/data/entregables). Sin esto, Claude Code lo trata como
        # fuera del proyecto y en modo dontAsk niega leer y escribir ahí.
        add_dirs=[str(config.ENTREGABLES_DIR.resolve())],
        setting_sources=["project"],
        skills=["campana-meta", "editar-campana", "analizar-campanas", "pieza-contenido"],
        system_prompt={"type": "preset", "preset": "claude_code", "append": INSTRUCCIONES},
        mcp_servers={"meta": meta_srv, "monday": monday_srv, "slack": slack_srv},
        allowed_tools=["Read", "Write", "Edit", "Glob", "Grep", "Bash", "Agent", "Task", "Skill", "TodoWrite",
                       "mcp__meta", "mcp__monday", "mcp__slack"],
        disallowed_tools=["AskUserQuestion", "WebFetch", "WebSearch", "NotebookEdit"],
        permission_mode="dontAsk",
        model=config.AGENT_MODEL,
        max_turns=config.MAX_TURNOS,
        max_budget_usd=config.MAX_USD_POR_EJECUCION,
        resume=session_id,
        hooks={"PreToolUse": [HookMatcher(matcher="Bash", hooks=[guardia_bash]),
                              HookMatcher(matcher="Write|Edit|MultiEdit", hooks=[guardia_archivos])]},
        env={"CLAUDE_CONFIG_DIR": str(config.DATA_DIR / "claude"), "CHROME": config.CHROME,
             "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"},
    )


def _agente_de_herramienta(nombre: str) -> str | None:
    if nombre.startswith("mcp__meta__"):
        return "operador-pauta"
    if nombre.startswith("mcp__monday__"):
        return "gestor-solicitudes"
    if nombre.startswith("mcp__slack__"):
        return "avisos"
    return None


async def ejecutar(ctx: Contexto, prompt: str) -> Resultado:
    """Corre (o continúa) la conversación del agente y devuelve su respuesta final."""
    candado = _candados.setdefault(ctx.conv_id, asyncio.Lock())
    async with candado, _semaforo:
        conv = db.obtener_conversacion(ctx.conv_id) or {}
        db.guardar_conversacion(ctx.conv_id, canal=ctx.canal, thread_ts=ctx.thread_ts, usuario=ctx.usuario,
                                estado="trabajando", item_monday=ctx.item_monday or conv.get("item_monday"),
                                titulo=conv.get("titulo") or prompt[:140])
        ejec_id = db.iniciar_ejecucion(ctx.conv_id)
        db.evento(ctx.conv_id, "orquestador", "inicio", prompt[:300])
        agentes_por_tool: dict[str, str] = {}
        final: ResultMessage | None = None
        session_id = conv.get("session_id")
        try:
            async for msg in query(prompt=prompt, options=_opciones(ctx, session_id)):
                if isinstance(msg, SystemMessage) and msg.subtype == "init":
                    sid = (getattr(msg, "data", {}) or {}).get("session_id")
                    if sid:
                        session_id = sid
                        db.guardar_conversacion(ctx.conv_id, session_id=sid)
                elif isinstance(msg, AssistantMessage):
                    padre = agentes_por_tool.get(msg.parent_tool_use_id or "", "orquestador")
                    for bloque in msg.content:
                        if not isinstance(bloque, ToolUseBlock):
                            continue
                        if bloque.name in ("Agent", "Task"):
                            agente = bloque.input.get("subagent_type") or "general"
                            agentes_por_tool[bloque.id] = agente
                            db.evento(ctx.conv_id, agente, "trabajando", bloque.input.get("description", ""))
                        elif bloque.name == "Skill":
                            db.evento(ctx.conv_id, "orquestador", "skill",
                                      str(bloque.input.get("skill") or bloque.input.get("command") or ""))
                        else:
                            agente = _agente_de_herramienta(bloque.name)
                            if agente:
                                db.evento(ctx.conv_id, agente if padre == "orquestador" else padre,
                                          bloque.name.split("__")[-1], "")
                elif isinstance(msg, ResultMessage):
                    final = msg
        except Exception as e:  # noqa: BLE001
            db.cerrar_ejecucion(ejec_id, "error", None, None, None, None, error=str(e))
            db.guardar_conversacion(ctx.conv_id, estado="error", aprobacion_vigente=False)
            db.evento(ctx.conv_id, "orquestador", "error", str(e)[:500])
            return Resultado(texto="", error=str(e), escrituras=ctx.escrituras)

        texto = (final.result if final else "") or ""
        pide = MARCA_APROBACION in texto
        texto = texto.replace(MARCA_APROBACION, "").strip()
        estado = "error" if (final and final.is_error) else ("esperando_aprobacion" if pide else "terminado")
        db.cerrar_ejecucion(ejec_id, estado, final.total_cost_usd if final else None,
                            final.usage if final else None, final.num_turns if final else None,
                            final.model_usage if final else None,
                            error=(final.subtype if final and final.is_error else None))
        db.guardar_conversacion(ctx.conv_id, estado=estado, aprobacion_vigente=False,
                                session_id=(final.session_id if final else session_id),
                                item_monday=ctx.item_monday or conv.get("item_monday"))
        for negado in (getattr(final, "permission_denials", None) or [])[:10]:
            db.evento(ctx.conv_id, "orquestador", "permiso_negado", str(negado)[:400])
        db.evento(ctx.conv_id, "orquestador", estado, f"costo ${final.total_cost_usd or 0:.3f}" if final else "")
        archivos = sorted(set(ARCHIVO_ENTREGABLE.findall(texto)))
        error = None
        if final and final.is_error:
            error = f"El agente terminó con error ({final.subtype})."
        return Resultado(texto=texto, pide_aprobacion=pide, costo_usd=(final.total_cost_usd or 0.0) if final else 0.0,
                         error=error, archivos=archivos, escrituras=ctx.escrituras)