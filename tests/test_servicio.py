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
    assert set(o.mcp_servers) == {"meta", "monday", "slack", "google_ads", "linkedin"} and o.cwd == str(config.AGENCIA_DIR)
    assert str(config.ENTREGABLES_DIR.resolve()) in o.add_dirs


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


def test_monday_notas_se_agregan(monkeypatch):
    llamadas = []

    async def gql_falso(consulta, variables=None):
        llamadas.append((consulta, variables))
        if consulta.startswith("query"):
            return {"items": [{"column_values": [{"id": "long_text_mm7vmg76", "text": "Nota previa"}]}]}
        return {"change_multiple_column_values": {"id": "1"}}

    monkeypatch.setattr(monday, "gql", gql_falso)
    monkeypatch.setattr(monday, "tablero_permitido", lambda b: True)
    ctx = Contexto(conv_id="c6", canal="C", thread_ts="1", usuario="U", aprobado=True)
    _, tools = monday.crear_servidor(ctx)
    r = correr(herramienta(tools, "monday_actualizar").handler(
        {"tablero_id": "18434029216", "item_id": "1",
         "valores_json": '{"long_text_mm7vmg76": "IDs nuevos", "link_mm7v50k2": "https://a.com"}'}))
    assert not r.get("is_error")
    enviados = __import__("json").loads(llamadas[-1][1]["v"])
    assert enviados["long_text_mm7vmg76"]["text"] == "Nota previa\n\nIDs nuevos"
    assert enviados["link_mm7v50k2"] == {"url": "https://a.com", "text": "Ver campaña en Ads Manager"}


class SlackFalso:
    def __init__(self):
        self.mensajes = []

    async def users_lookupByEmail(self, email):
        if email.endswith("@sin-slack.com"):
            raise RuntimeError("users_not_found")
        return {"user": {"id": "U_" + email.split("@")[0].upper()}}

    async def chat_postMessage(self, channel, text, **_):
        self.mensajes.append((channel, text))
        return {"ts": "1"}


def _gql_avisos(creador_id="77"):
    async def gql(consulta, variables=None):
        if "me {" in consulta:
            return {"me": {"id": "1"}}          # usuario del token (el agente)
        if "users(ids" in consulta:
            return {"users": [{"email": "solicita@freelan.com.mx"}]}
        return {"items": [{"id": "9", "name": "Campaña X", "url": "https://monday.com/x", "board": {"id": "18434029216"},
                           "creator": {"id": creador_id, "name": "Ana", "email": "ana@freelan.com.mx"},
                           "column_values": [
                               {"id": config.MONDAY_COLUMNA_SOLICITANTE, "text": "Sol",
                                "value": '{"personsAndTeams":[{"id":5,"kind":"person"}]}'},
                               {"id": config.MONDAY_COLUMNA_NOTAS, "text": "Falta la URL en B10", "value": None}]}]}
    return gql


def test_aviso_error_va_al_creador_y_solicitante(monkeypatch):
    from app import avisos
    monkeypatch.setattr(avisos, "_usuario_servicio", None)
    monkeypatch.setattr(avisos.monday, "gql", _gql_avisos())
    monkeypatch.setattr(config, "SLACK_CANAL_AVISOS", "CAVISOS")
    s = SlackFalso()
    r = correr(avisos.avisar_problema(s, "9", "Error"))
    assert r["enviados"] == ["solicita@freelan.com.mx", "ana@freelan.com.mx"]
    assert any(c == "U_ANA" and "Falta la URL en B10" in t for c, t in s.mensajes)
    assert any(c == "CAVISOS" for c, _ in s.mensajes)


def test_aviso_nuevo_a_responsable_y_no_si_lo_crea_el_agente(monkeypatch):
    from app import avisos
    monkeypatch.setattr(avisos, "_usuario_servicio", None)
    monkeypatch.setattr(avisos.monday, "gql", _gql_avisos())
    monkeypatch.setattr(config, "SLACK_CANAL_AVISOS", "CAVISOS")
    monkeypatch.setattr(config, "SLACK_RESPONSABLE_EMAIL", "majo@freelan.com.mx")
    s = SlackFalso()
    r = correr(avisos.avisar_nuevo(s, {"pulseId": 9, "userId": 77}))
    assert set(r["enviados"]) == {"canal", "responsable"}
    assert any(c == "U_MAJO" and "Nueva solicitud" in t for c, t in s.mensajes)
    s2 = SlackFalso()
    r = correr(avisos.avisar_nuevo(s2, {"pulseId": 9, "userId": 1}))
    assert r.get("ignorado") and not s2.mensajes


# ------------------------------------------------------------------ Google Ads
import datetime as _dt  # noqa: E402
import json as _json  # noqa: E402

from app.tools import google_ads  # noqa: E402


def _spec_google(**extra):
    hoy = _dt.date.today()
    spec = {"cuenta": "370-169-8329", "nombre": "[PRUEBA-AGENTE] RevOps · Búsqueda", "presupuesto_diario_mxn": 100,
            "inicio": (hoy + _dt.timedelta(days=3)).isoformat(), "fin": (hoy + _dt.timedelta(days=20)).isoformat(),
            "negativas_campana": ["gratis", "empleo"],
            "grupos": [{"nombre": "RevOps HubSpot",
                        "palabras_clave": [{"texto": "consultoría revops", "concordancia": "FRASE"},
                                           {"texto": "implementación hubspot", "concordancia": "EXACTA"}],
                        "anuncios": [{"titulos": ["Arquitectura RevOps", "Partner de HubSpot", "Agenda una charla"],
                                      "descripciones": ["Unifica marketing y ventas en un solo sistema.",
                                                        "Diseñamos el proceso antes de automatizar."],
                                      "url_final": "https://freelan.com.mx/contacto", "ruta1": "revops"}]}]}
    spec.update(extra)
    return spec


def test_google_armar_busqueda_valida_y_pausa(monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_ADS_CUENTAS_PERMITIDAS", ["3701698329"])
    errores, ops, resumen = google_ads.armar_busqueda(_spec_google())
    assert errores == []
    campana = next(o["campaignOperation"]["create"] for o in ops if "campaignOperation" in o)
    assert campana["status"] == "PAUSED" and campana["advertisingChannelType"] == "SEARCH"
    assert campana["containsEuPoliticalAdvertising"] == "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING"
    assert campana["startDateTime"].endswith(" 00:00:00") and campana["endDateTime"].endswith(" 23:59:59")
    presupuesto = ops[0]["campaignBudgetOperation"]["create"]
    assert presupuesto["amountMicros"] == "100000000"
    assert any(o.get("campaignCriterionOperation", {}).get("create", {}).get("location") for o in ops)
    assert resumen["anuncios"] == 1 and resumen["estatus_campana"] == "PAUSED"


def test_google_armar_busqueda_detecta_errores(monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_ADS_CUENTAS_PERMITIDAS", ["3701698329"])
    monkeypatch.setattr(config, "GOOGLE_ADS_PRESUPUESTO_MAX_DIARIO", 500.0)
    spec = _spec_google(presupuesto_diario_mxn=9000, cuenta="111-222-3333")
    spec["grupos"][0]["anuncios"][0]["titulos"] = ["Un título que es demasiado largo para Google Ads", "Dos"]
    errores, _, _ = google_ads.armar_busqueda(spec)
    texto = " | ".join(errores)
    assert "no permitida" in texto and "tope" in texto and "máximo 30" in texto and "deben ser de 3 a 15" in texto


def test_google_montar_bloquea_sin_aprobacion(monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_ADS_CUENTAS_PERMITIDAS", ["3701698329"])
    ctx = Contexto(conv_id="g1", canal="C", thread_ts="1", usuario="U")
    _, tools = google_ads.crear_servidor(ctx)
    r = correr(herramienta(tools, "google_ads_montar_busqueda").handler({"campana_json": _json.dumps(_spec_google())}))
    assert r.get("is_error") and "aprobación" in r["content"][0]["text"]


def test_google_montar_modo_prueba_usa_validate_only(monkeypatch):
    llamadas = []

    async def llamar_falso(metodo, ruta, cuerpo=None):
        llamadas.append((ruta, cuerpo))
        if ruta.endswith("googleAds:search"):
            if "currency_code" in cuerpo["query"]:
                return {"results": [{"customer": {"currencyCode": "MXN"}}]}
            return {"results": []}
        return {}

    monkeypatch.setattr(config, "GOOGLE_ADS_CUENTAS_PERMITIDAS", ["3701698329"])
    monkeypatch.setattr(config, "MODO_PRUEBA", True)
    monkeypatch.setattr(google_ads, "configurado", lambda: True)
    monkeypatch.setattr(google_ads, "llamar", llamar_falso)
    ctx = Contexto(conv_id="g2", canal="C", thread_ts="1", usuario="U", aprobado=True)
    _, tools = google_ads.crear_servidor(ctx)
    r = correr(herramienta(tools, "google_ads_montar_busqueda").handler({"campana_json": _json.dumps(_spec_google())}))
    assert not r.get("is_error"), r
    mutate = [c for ruta, c in llamadas if ruta.endswith("googleAds:mutate")]
    assert len(mutate) == 1 and mutate[0]["validateOnly"] is True
    assert "validado_por_google" in r["content"][0]["text"]


def test_google_montar_rechaza_duplicado_y_moneda(monkeypatch):
    async def llamar_dup(metodo, ruta, cuerpo=None):
        if "currency_code" in cuerpo["query"]:
            return {"results": [{"customer": {"currencyCode": "MXN"}}]}
        return {"results": [{"campaign": {"id": "99", "status": "PAUSED"}}]}

    async def llamar_usd(metodo, ruta, cuerpo=None):
        return {"results": [{"customer": {"currencyCode": "USD"}}]}

    monkeypatch.setattr(config, "GOOGLE_ADS_CUENTAS_PERMITIDAS", ["3701698329"])
    monkeypatch.setattr(google_ads, "configurado", lambda: True)
    ctx = Contexto(conv_id="g3", canal="C", thread_ts="1", usuario="U", aprobado=True)
    _, tools = google_ads.crear_servidor(ctx)
    montar = herramienta(tools, "google_ads_montar_busqueda").handler
    monkeypatch.setattr(google_ads, "llamar", llamar_dup)
    r = correr(montar({"campana_json": _json.dumps(_spec_google())}))
    assert r.get("is_error") and "Ya existe" in r["content"][0]["text"]
    monkeypatch.setattr(google_ads, "llamar", llamar_usd)
    r = correr(montar({"campana_json": _json.dumps(_spec_google())}))
    assert r.get("is_error") and "USD" in r["content"][0]["text"]


def test_google_pausar_y_consultar_candados(monkeypatch):
    enviados = []

    async def llamar_falso(metodo, ruta, cuerpo=None):
        enviados.append(cuerpo)
        return {"mutateOperationResponses": [{"campaignResult": {"resourceName": "customers/3701698329/campaigns/5"}}]}

    monkeypatch.setattr(config, "GOOGLE_ADS_CUENTAS_PERMITIDAS", ["3701698329"])
    monkeypatch.setattr(config, "MODO_PRUEBA", False)
    monkeypatch.setattr(google_ads, "configurado", lambda: True)
    monkeypatch.setattr(google_ads, "llamar", llamar_falso)
    ctx = Contexto(conv_id="g4", canal="C", thread_ts="1", usuario="U", aprobado=True)
    _, tools = google_ads.crear_servidor(ctx)
    r = correr(herramienta(tools, "google_ads_pausar").handler({"recurso": "customers/3701698329/campaigns/5"}))
    assert not r.get("is_error")
    op = enviados[-1]["mutateOperations"][0]["campaignOperation"]
    assert op["update"]["status"] == "PAUSED" and op["updateMask"] == "status"
    r = correr(herramienta(tools, "google_ads_pausar").handler({"recurso": "customers/999/campaigns/5"}))
    assert r.get("is_error")
    r = correr(herramienta(tools, "google_ads_consultar").handler(
        {"cuenta": "3701698329", "gaql": "DELETE campaign"}))
    assert r.get("is_error") and "SELECT" in r["content"][0]["text"]
    # Anuncio agregado a un grupo existente: siempre en pausa
    r = correr(herramienta(tools, "google_ads_agregar_anuncio").handler(
        {"cuenta": "3701698329", "grupo": "77", "anuncio_json": _json.dumps(_spec_google()["grupos"][0]["anuncios"][0])}))
    assert not r.get("is_error")
    assert enviados[-1]["mutateOperations"][0]["adGroupAdOperation"]["create"]["status"] == "PAUSED"


def test_opciones_incluyen_google_ads():
    ctx = Contexto(conv_id="g5", canal="C", thread_ts="1", usuario="U")
    o = runner._opciones(ctx, None)
    assert "google_ads" in o.mcp_servers and "mcp__google_ads" in o.allowed_tools


# ------------------------------------------------------------------ LinkedIn
from app.tools import linkedin  # noqa: E402


def _spec_linkedin(**extra):
    hoy = _dt.date.today()
    spec = {"cuenta": "519998414", "nombre": "[PRUEBA-AGENTE] RevOps · LinkedIn", "objetivo": "VISITAS_SITIO",
            "presupuesto_diario": 200, "puja": {"tipo": "CPC", "monto": 45},
            "inicio": (hoy + _dt.timedelta(days=3)).isoformat(), "fin": (hoy + _dt.timedelta(days=20)).isoformat(),
            "segmentacion": {"ubicaciones": ["urn:li:geo:103323778"], "seniority": ["urn:li:seniority:6"],
                             "excluir": {"funciones": ["urn:li:function:12"]}},
            "anuncios": [{"texto": "Unifica marketing y ventas en un solo sistema.", "titulo": "Arquitectura RevOps",
                          "url": "https://freelan.com.mx/contacto", "cta": "LEARN_MORE",
                          "imagen": "https://files.monday.com/arte.png"}]}
    spec.update(extra)
    return spec


def test_linkedin_armar_en_draft(monkeypatch):
    monkeypatch.setattr(config, "LINKEDIN_CUENTAS_PERMITIDAS", ["519998414"])
    errores, avisos, plan = linkedin.armar_campana(_spec_linkedin())
    assert errores == []
    c = plan["campana"]
    assert c["status"] == "DRAFT" and plan["grupo"]["status"] == "DRAFT"
    assert c["objectiveType"] == "WEBSITE_VISIT" and c["dailyBudget"] == {"amount": "200.00", "currencyCode": "MXN"}
    assert c["runSchedule"]["start"] < c["runSchedule"]["end"]
    inc = c["targetingCriteria"]["include"]["and"]
    assert {"or": {"urn:li:adTargetingFacet:locations": ["urn:li:geo:103323778"]}} in inc
    assert "urn:li:adTargetingFacet:jobFunctions" in c["targetingCriteria"]["exclude"]["or"]


def test_linkedin_armar_detecta_errores(monkeypatch):
    monkeypatch.setattr(config, "LINKEDIN_CUENTAS_PERMITIDAS", ["519998414"])
    spec = _spec_linkedin(cuenta="111", presupuesto_diario=99999, segmentacion={"cargos": ["Director de marketing"]})
    spec["anuncios"][0].update(cta="COMPRA", url="http://x.com", texto="x" * 700)
    errores, _, _ = linkedin.armar_campana(spec)
    texto = " | ".join(errores)
    for esperado in ("no permitida", "tope", "URNs", "ubicación", "CTA", "https://", "máximo 600"):
        assert esperado in texto, esperado


def test_linkedin_montar_bloqueos_y_modo_prueba(monkeypatch):
    monkeypatch.setattr(config, "LINKEDIN_CUENTAS_PERMITIDAS", ["519998414"])
    ctx = Contexto(conv_id="l1", canal="C", thread_ts="1", usuario="U")
    _, tools = linkedin.crear_servidor(ctx)
    montar = herramienta(tools, "linkedin_montar_campana").handler
    r = correr(montar({"campana_json": _json.dumps(_spec_linkedin())}))
    assert r.get("is_error") and "aprobación" in r["content"][0]["text"]
    monkeypatch.setattr(config, "MODO_PRUEBA", True)
    monkeypatch.setattr(linkedin, "configurado", lambda: False)
    ctx2 = Contexto(conv_id="l2", canal="C", thread_ts="1", usuario="U", aprobado=True)
    _, tools2 = linkedin.crear_servidor(ctx2)
    r = correr(herramienta(tools2, "linkedin_montar_campana").handler({"campana_json": _json.dumps(_spec_linkedin())}))
    assert not r.get("is_error") and '"DRAFT"' in r["content"][0]["text"] and "modo_prueba" in r["content"][0]["text"]


def test_linkedin_montar_real_y_limpieza(monkeypatch):
    llamadas = []

    async def llamar_ok(metodo, ruta, cuerpo=None, consulta="", extra=None):
        llamadas.append((metodo, ruta, cuerpo))
        if metodo == "GET" and ruta == "adAccounts/519998414":
            return {"currency": "MXN", "reference": "urn:li:organization:42", "name": "Freelan"}, {}
        if ruta == "images":
            return {"value": {"uploadUrl": "https://up.linkedin.com/x", "image": "urn:li:image:I1"}}, {}
        if metodo == "GET" and ruta.startswith("images/"):
            return {"status": "AVAILABLE"}, {}
        ids = {"posts": "urn:li:share:P1", "adAccounts/519998414/adCampaignGroups": "urn:li:sponsoredCampaignGroup:11",
               "adAccounts/519998414/adCampaigns": "urn:li:sponsoredCampaign:7",
               "adAccounts/519998414/creatives": "urn:li:sponsoredCreative:C1"}
        return {}, {"x-restli-id": ids.get(ruta, "")}

    class Resp:
        status_code = 201

    class ClienteFalso:
        def __init__(self, *a, **k): ...
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url):
            class R:
                content = b"\x89PNG\r\n\x1a\nDATOS"
                is_redirect = False
                headers = {}
                def raise_for_status(self): ...
            return R()
        async def put(self, url, content=None, headers=None): return Resp()

    monkeypatch.setattr(config, "LINKEDIN_CUENTAS_PERMITIDAS", ["519998414"])
    monkeypatch.setattr(config, "MODO_PRUEBA", False)
    monkeypatch.setattr(config, "LINKEDIN_ACCESS_TOKEN", "t")
    monkeypatch.setattr(linkedin, "llamar", llamar_ok)
    monkeypatch.setattr(linkedin.httpx, "AsyncClient", ClienteFalso)
    ctx = Contexto(conv_id="l3", canal="C", thread_ts="1", usuario="U", aprobado=True)
    _, tools = linkedin.crear_servidor(ctx)
    r = correr(herramienta(tools, "linkedin_montar_campana").handler({"campana_json": _json.dumps(_spec_linkedin())}))
    assert not r.get("is_error"), r
    post = next(c for m, ruta, c in llamadas if ruta == "posts")
    assert post["distribution"]["feedDistribution"] == "NONE" and post["author"] == "urn:li:organization:42"
    camp = next(c for m, ruta, c in llamadas if ruta.endswith("adCampaigns"))
    assert camp["status"] == "DRAFT" and camp["campaignGroup"] == "urn:li:sponsoredCampaignGroup:11"
    creativo = next(c for m, ruta, c in llamadas if ruta.endswith("creatives"))
    assert creativo["intendedStatus"] == "DRAFT"

    # Falla al crear el creativo → se borran campaña y grupo en DRAFT
    borrados = []

    async def llamar_falla(metodo, ruta, cuerpo=None, consulta="", extra=None):
        if metodo == "DELETE":
            borrados.append(ruta)
            return {}, {}
        if ruta.endswith("creatives"):
            raise linkedin.ErrorLinkedIn("HTTP 400 creativo rechazado")
        return await llamar_ok(metodo, ruta, cuerpo, consulta, extra)

    monkeypatch.setattr(linkedin, "llamar", llamar_falla)
    r = correr(herramienta(tools, "linkedin_montar_campana").handler({"campana_json": _json.dumps(_spec_linkedin())}))
    assert r.get("is_error")
    assert "adAccounts/519998414/adCampaigns/7" in borrados and "adAccounts/519998414/adCampaignGroups/11" in borrados


def test_linkedin_pausar_y_consultar_candados(monkeypatch):
    enviados = []

    async def llamar_falso(metodo, ruta, cuerpo=None, consulta="", extra=None):
        if metodo == "GET":
            if "creatives" in ruta:
                return {"campaign": "urn:li:sponsoredCampaign:7"}, {}
            return {"account": "urn:li:sponsoredAccount:519998414"}, {}
        enviados.append((ruta, cuerpo, extra))
        return {}, {}

    monkeypatch.setattr(config, "LINKEDIN_CUENTAS_PERMITIDAS", ["519998414"])
    monkeypatch.setattr(config, "MODO_PRUEBA", False)
    monkeypatch.setattr(linkedin, "llamar", llamar_falso)
    ctx = Contexto(conv_id="l4", canal="C", thread_ts="1", usuario="U", aprobado=True)
    _, tools = linkedin.crear_servidor(ctx)
    pausar = herramienta(tools, "linkedin_pausar").handler
    r = correr(pausar({"cuenta": "519998414", "tipo": "creativo", "id": "urn:li:sponsoredCreative:55", "estatus": "PAUSED"}))
    assert not r.get("is_error")
    ruta, cuerpo, extra = enviados[-1]
    assert ruta.endswith("creatives/urn%3Ali%3AsponsoredCreative%3A55")
    assert cuerpo == {"patch": {"$set": {"intendedStatus": "PAUSED"}}} and extra["X-RestLi-Method"] == "PARTIAL_UPDATE"
    r = correr(pausar({"cuenta": "519998414", "tipo": "campana", "id": "7", "estatus": "ACTIVE"}))
    assert r.get("is_error")
    consultar = herramienta(tools, "linkedin_consultar").handler
    assert correr(consultar({"ruta": "adAccounts/999/adCampaigns"})).get("is_error")
    assert correr(consultar({"ruta": "people/me"})).get("is_error")
    assert correr(consultar({"ruta": "adAnalytics", "consulta": "q=analytics&accounts=List(urn%3Ali%3AsponsoredAccount%3A999)"})).get("is_error")
    assert not correr(consultar({"ruta": "adTargetingEntities", "consulta": "q=typeahead&query=marketing"})).get("is_error")



def test_linkedin_consultar_no_se_puede_saltar_la_cuenta(monkeypatch):
    async def llamar_falso(metodo, ruta, cuerpo=None, consulta="", extra=None):
        return {"account": "urn:li:sponsoredAccount:999"}, {}

    monkeypatch.setattr(config, "LINKEDIN_CUENTAS_PERMITIDAS", ["519998414"])
    monkeypatch.setattr(config, "MODO_PRUEBA", False)
    monkeypatch.setattr(linkedin, "llamar", llamar_falso)
    ctx = Contexto(conv_id="l5", canal="C", thread_ts="1", usuario="U", aprobado=True)
    _, tools = linkedin.crear_servidor(ctx)
    consultar = herramienta(tools, "linkedin_consultar").handler
    bloqueadas = [
        {"ruta": "adTargetingEntities/../adAccounts/999/adCampaigns"},
        {"ruta": "adAccounts/519998414/../999/adCampaigns"},
        {"ruta": "posts", "consulta": "q=author&author=urn:li:organization:1"},
        {"ruta": "adAnalytics", "consulta": "q=analytics&accounts=List(urn%3Ali%3AsponsoredAccount%3a999,urn%3Ali%3AsponsoredAccount%3A519998414)"},
        {"ruta": "adAnalytics", "consulta": "q=analytics&accounts=List(urn%253Ali%253Asponsored%2541ccount%253A999)"},
        {"ruta": "adAnalytics", "consulta": "q=analytics&accounts=List(urn%3Ali%3AsponsoredAccount%3A519998414)&campaigns=List(urn%3Ali%3AsponsoredCampaign%3A5)"},
    ]
    for args in bloqueadas:
        assert correr(consultar(args)).get("is_error"), args
    assert not correr(consultar({"ruta": "adAnalytics", "consulta":
        "q=analytics&pivot=CAMPAIGN&accounts=List(urn%3Ali%3AsponsoredAccount%3A519998414)"})).get("is_error")
    # Pausar algo de otra cuenta aunque la ruta nombre la permitida
    r = correr(herramienta(tools, "linkedin_pausar").handler(
        {"cuenta": "519998414", "tipo": "campana", "id": "7", "estatus": "PAUSED"}))
    assert r.get("is_error") and "no pertenece" in r["content"][0]["text"]


def test_numeros_invalidos_y_escape(monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_ADS_CUENTAS_PERMITIDAS", ["3701698329"])
    monkeypatch.setattr(config, "LINKEDIN_CUENTAS_PERMITIDAS", ["519998414"])
    errores, _, _ = google_ads.armar_busqueda(_spec_google(presupuesto_diario_mxn=float("nan"), cpc_max_mxn="mucho"))
    assert any("presupuesto" in e for e in errores) and any("cpc_max_mxn" in e for e in errores)
    errores, _, _ = linkedin.armar_campana(_spec_linkedin(presupuesto_diario=float("nan"), puja={"tipo": "CPC", "monto": -3}))
    assert any("presupuesto" in e for e in errores) and any("puja" in e for e in errores)
    assert linkedin.escapar_texto("Hola (B2B) @equipo #1") == "Hola \\(B2B\\) \\@equipo \\#1"


def test_google_no_lee_el_mcc(monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_ADS_CUENTAS_PERMITIDAS", ["3701698329"])
    monkeypatch.setattr(config, "GOOGLE_ADS_LOGIN_CUSTOMER_ID", "2240203724")
    ctx = Contexto(conv_id="g6", canal="C", thread_ts="1", usuario="U")
    _, tools = google_ads.crear_servidor(ctx)
    r = correr(herramienta(tools, "google_ads_consultar").handler(
        {"cuenta": "2240203724", "gaql": "SELECT customer_client.id FROM customer_client"}))
    assert r.get("is_error")


def test_descarga_de_imagen_solo_hosts_permitidos():
    from app.tools.comun import descargar_imagen, host_permitido
    hosts = ["monday.com", "files-monday-com.s3.amazonaws.com"]
    assert host_permitido("https://files-monday-com.s3.amazonaws.com/a.png?x=1", hosts)
    assert host_permitido("https://abc.monday.com/a.png", hosts)
    assert not host_permitido("http://files-monday-com.s3.amazonaws.com/a.png", hosts)
    assert not host_permitido("https://169.254.169.254/latest", hosts)
    assert not host_permitido("https://evilmonday.com/a.png", hosts)
    try:
        correr(descargar_imagen("https://127.0.0.1/a.png", hosts))
        assert False
    except ValueError:
        pass
