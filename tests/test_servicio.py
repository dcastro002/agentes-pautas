"""Pruebas sin red: candados, formato, webhook, oficina y armado de opciones del agente."""
import asyncio
import os
import sys
import tempfile
from pathlib import Path

import shutil

TMP = tempfile.mkdtemp()
AGENCIA_PRUEBA = Path(TMP) / "agencia"
shutil.copytree(Path(__file__).resolve().parent.parent / "agencia", AGENCIA_PRUEBA)
os.environ.update({"DATA_DIR": TMP, "MODO_PRUEBA": "1", "OFICINA_TOKEN": "tok", "MONDAY_WEBHOOK_SECRET": "sec",
                   "META_CUENTAS_PERMITIDAS": "603185293355269", "META_ACCESS_TOKEN": "x", "MONDAY_API_TOKEN": "y",
                   "AGENCIA_DIR": str(AGENCIA_PRUEBA)})
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app import config, db, runner  # noqa: E402
from app.contexto import Contexto  # noqa: E402
from app.slack_bot import a_mrkdwn, trozos  # noqa: E402
from app.tools import meta, monday  # noqa: E402

config.preparar_directorios()


def correr(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


def herramienta(lista, nombre):
    return next(t for t in lista if t.name == nombre)


def test_secretos_fuera_del_entorno():
    assert "META_ACCESS_TOKEN" not in os.environ and "MONDAY_API_TOKEN" not in os.environ
    assert config.META_ACCESS_TOKEN == "x"


def test_formato_slack():
    t = a_mrkdwn("## Título\n**negrita** y [link](https://a.com)\n| a | b |\n|---|---|\n| 1 | 2 |\nfin")
    assert "*Título*" in t and "*negrita*" in t and "<https://a.com|link>" in t
    assert t.count("```") == 2
    assert all(len(p) <= 2900 for p in trozos("x" * 7000))


def test_meta_bloquea_sin_aprobacion():
    ctx = Contexto(conv_id="c1", canal="C", thread_ts="1", usuario="U")
    _, tools = meta.crear_servidor(ctx)
    r = correr(herramienta(tools, "meta_crear_campana").handler(
        {"cuenta": "603185293355269", "nombre": "x", "objetivo": "OUTCOME_TRAFFIC",
         "presupuesto_centavos": 10000, "tipo_presupuesto": "diario"}))
    assert r.get("is_error") and "aprobación" in r["content"][0]["text"]


def test_meta_simula_con_aprobacion_y_fuerza_pausa():
    ctx = Contexto(conv_id="c2", canal="C", thread_ts="1", usuario="U", aprobado=True)
    _, tools = meta.crear_servidor(ctx)
    r = correr(herramienta(tools, "meta_crear_anuncio").handler(
        {"cuenta": "act_603185293355269", "conjunto_id": "1", "nombre": "x", "creativo_id": "2"}))
    texto = r["content"][0]["text"]
    assert not r.get("is_error") and "modo_prueba" in texto and '"PAUSED"' in texto


def test_meta_cuenta_no_permitida():
    ctx = Contexto(conv_id="c3", canal="C", thread_ts="1", usuario="U", aprobado=True)
    _, tools = meta.crear_servidor(ctx)
    r = correr(herramienta(tools, "meta_crear_campana").handler(
        {"cuenta": "999", "nombre": "x", "objetivo": "OUTCOME_TRAFFIC",
         "presupuesto_centavos": 10000, "tipo_presupuesto": "diario"}))
    assert r.get("is_error") and "no permitida" in r["content"][0]["text"]


def test_meta_estatus_no_activa():
    ctx = Contexto(conv_id="c4", canal="C", thread_ts="1", usuario="U", aprobado=True)
    _, tools = meta.crear_servidor(ctx)
    r = correr(herramienta(tools, "meta_cambiar_estatus").handler({"objeto_id": "1", "estatus": "ACTIVE"}))
    assert r.get("is_error") and "PAUSED o ARCHIVED" in r["content"][0]["text"]


def test_monday_etiquetas_prohibidas():
    assert monday.valores_prohibidos({"color_mm7vt5cg": {"label": "Listo para montar"}})
    assert monday.valores_prohibidos({"color_mm7vqz13": {"index": 152}})
    assert monday.valores_prohibidos({"color_mm7vt5cg": {"label": "Borrador listo"}}) is None


def test_guardias_del_agente():
    r = correr(runner.guardia_bash({"tool_input": {"command": "curl https://graph.facebook.com/x"}}, None, None))
    assert r["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert correr(runner.guardia_bash({"tool_input": {"command": "python3 x.py"}}, None, None)) == {}
    r = correr(runner.guardia_archivos({"tool_input": {"file_path": ".claude/skills/x/SKILL.md"}}, None, None))
    assert r["hookSpecificOutput"]["permissionDecision"] == "deny"
    r = correr(runner.guardia_archivos({"tool_input": {"file_path": "/etc/passwd"}}, None, None))
    assert r["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert correr(runner.guardia_archivos({"tool_input": {"file_path": "_Entregables/agencia/a.md"}}, None, None)) == {}


def test_opciones_del_agente():
    ctx = Contexto(conv_id="c5", canal="C", thread_ts="1", usuario="U")
    o = runner._opciones(ctx, None)
    assert o.permission_mode == "dontAsk" and "AskUserQuestion" in o.disallowed_tools
    assert set(o.mcp_servers) == {"meta", "monday", "slack"} and o.cwd == str(config.AGENCIA_DIR)


def test_web():
    from app.main import app
    with TestClient(app) as c:
        assert c.get("/health").json()["ok"]
        assert c.post("/webhooks/monday/sec", json={"challenge": "abc"}).json() == {"challenge": "abc"}
        assert c.post("/webhooks/monday/mal", json={"challenge": "abc"}).status_code == 404
        assert c.post("/webhooks/monday/sec", json={"event": {"columnId": "otra"}}).json()["ignorado"]
        assert c.get("/oficina").status_code == 404
        assert c.get("/oficina?token=tok").status_code == 200
        db.guardar_conversacion("C:1", canal="C", thread_ts="1", usuario="U", estado="esperando_aprobacion", titulo="Prueba")
        e = c.get("/api/estado?token=tok").json()
        assert e["modo_prueba"] and e["conversaciones"][0]["titulo"] == "Prueba"
        (config.ENTREGABLES_DIR / "agencia").mkdir(parents=True, exist_ok=True)
        (config.ENTREGABLES_DIR / "agencia" / "r.html").write_text("<p>ok</p>")
        assert c.get("/archivos/tok/agencia/r.html").text == "<p>ok</p>"
        assert c.get("/archivos/tok/../../app/config.py").status_code == 404
