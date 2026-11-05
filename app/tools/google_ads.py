"""Herramientas de Google Ads (API REST) con candados.

Candados en código, no en instrucciones:
- La campaña se crea siempre en PAUSED. No existe ninguna herramienta para activar nada:
  la única que cambia estatus solo acepta PAUSED.
- Lo que se agrega a una campaña existente (anuncios, palabras clave) se crea en PAUSED.
- El montaje es atómico: presupuesto, campaña, segmentación, grupos, palabras clave y anuncios
  van en UNA sola llamada. Si Google rechaza cualquier pieza, no se crea nada (no quedan
  campañas a medias).
- Solo cuentas de GOOGLE_ADS_CUENTAS_PERMITIDAS, moneda esperada y presupuesto bajo el tope.
- Toda escritura exige aprobación humana vigente (ctx.aprobado).
- En MODO_PRUEBA las escrituras se mandan con validateOnly: Google valida todo de verdad
  y no crea nada.
"""
import json
import re
import time
from datetime import date

import httpx
from claude_agent_sdk import create_sdk_mcp_server, tool

from .. import config, db
from ..contexto import Contexto
from .comun import cargar_json, error, esquema, numero_positivo, ok

API = "https://googleads.googleapis.com"
TOKEN_URL = "https://oauth2.googleapis.com/token"

# Límites de la red de búsqueda (anuncio responsivo de búsqueda y palabras clave)
TITULOS_MIN, TITULOS_MAX, TITULO_LARGO = 3, 15, 30
DESCRIPCIONES_MIN, DESCRIPCIONES_MAX, DESCRIPCION_LARGO = 2, 4, 90
RUTA_LARGO = 15
PALABRA_LARGO, PALABRA_MAX_PALABRAS = 80, 10
MAX_GRUPOS, MAX_ANUNCIOS_POR_GRUPO = 20, 3

CONCORDANCIAS = {"EXACTA": "EXACT", "EXACT": "EXACT", "FRASE": "PHRASE", "PHRASE": "PHRASE",
                 "AMPLIA": "BROAD", "BROAD": "BROAD"}
UBICACION_MEXICO = "geoTargetConstants/2484"
IDIOMA_ESPANOL = "languageConstants/1003"
RECURSO_PAUSABLE = re.compile(r"^customers/(\d+)/(campaigns|adGroups|adGroupAds|adGroupCriteria)/[\d~]+$")
OPERACION_POR_RECURSO = {"campaigns": "campaignOperation", "adGroups": "adGroupOperation",
                         "adGroupAds": "adGroupAdOperation", "adGroupCriteria": "adGroupCriterionOperation"}

_token: dict = {"valor": None, "vence": 0.0}


class ErrorGoogleAds(RuntimeError):
    pass


# ------------------------------------------------------------------ conexión
def configurado() -> bool:
    return bool(config.GOOGLE_ADS_CLIENT_ID and config.GOOGLE_ADS_CLIENT_SECRET and config.GOOGLE_ADS_REFRESH_TOKEN)


def _cid(cuenta) -> str:
    return re.sub(r"\D", "", str(cuenta or ""))


def cuenta_permitida(cuenta) -> bool:
    return bool(config.GOOGLE_ADS_CUENTAS_PERMITIDAS) and _cid(cuenta) in config.GOOGLE_ADS_CUENTAS_PERMITIDAS


async def _access_token() -> str:
    if _token["valor"] and time.time() < _token["vence"] - 120:
        return _token["valor"]
    async with httpx.AsyncClient(timeout=30) as cli:
        r = await cli.post(TOKEN_URL, data={"client_id": config.GOOGLE_ADS_CLIENT_ID,
                                            "client_secret": config.GOOGLE_ADS_CLIENT_SECRET,
                                            "refresh_token": config.GOOGLE_ADS_REFRESH_TOKEN,
                                            "grant_type": "refresh_token"})
    cuerpo = r.json() if r.content else {}
    if r.status_code >= 400 or "access_token" not in cuerpo:
        # Nunca se incluyen los valores enviados: solo el código de error de Google.
        raise ErrorGoogleAds(f"No pude renovar el acceso a Google ({cuerpo.get('error', r.status_code)}: "
                             f"{cuerpo.get('error_description', '')}). Revisa GOOGLE_ADS_REFRESH_TOKEN.")
    _token.update(valor=cuerpo["access_token"], vence=time.time() + int(cuerpo.get("expires_in", 3600)))
    return _token["valor"]


def _formatear_error(cuerpo: dict, estado: int) -> str:
    e = cuerpo.get("error", cuerpo) if isinstance(cuerpo, dict) else {}
    partes = [f"HTTP {estado}", str(e.get("status", "")), str(e.get("message", ""))[:300]]
    for detalle in e.get("details", []) or []:
        for err in detalle.get("errors", []) or []:
            codigo = ", ".join(f"{k}={v}" for k, v in (err.get("errorCode") or {}).items())
            campo = ".".join(str(p.get("fieldName", "")) + (f"[{p['index']}]" if "index" in p else "")
                             for p in ((err.get("location") or {}).get("fieldPathElements") or []))
            partes.append(f"· {codigo}: {err.get('message', '')}" + (f" (campo: {campo})" if campo else ""))
    return " ".join(p for p in partes if p)


async def llamar(metodo: str, ruta: str, cuerpo: dict | None = None) -> dict:
    if not configurado():
        raise ErrorGoogleAds("Google Ads no está configurado en el servidor (faltan GOOGLE_ADS_CLIENT_ID, "
                             "GOOGLE_ADS_CLIENT_SECRET o GOOGLE_ADS_REFRESH_TOKEN).")
    encabezados = {"Authorization": f"Bearer {await _access_token()}", "Content-Type": "application/json"}
    if config.GOOGLE_ADS_LOGIN_CUSTOMER_ID:
        encabezados["login-customer-id"] = config.GOOGLE_ADS_LOGIN_CUSTOMER_ID
    if config.GOOGLE_ADS_DEVELOPER_TOKEN:
        encabezados["developer-token"] = config.GOOGLE_ADS_DEVELOPER_TOKEN
    async with httpx.AsyncClient(timeout=120) as cli:
        r = await cli.request(metodo, f"{API}/{config.GOOGLE_ADS_API_VERSION}/{ruta}", headers=encabezados,
                              json=cuerpo)
    try:
        datos = r.json() if r.content else {}
    except Exception:
        datos = {"error": {"message": r.text[:500]}}
    if r.status_code >= 400:
        raise ErrorGoogleAds(_formatear_error(datos, r.status_code))
    return datos


async def buscar(cuenta: str, gaql: str, limite: int = 1000) -> list[dict]:
    filas, token = [], None
    while True:
        cuerpo = {"query": gaql}
        if token:
            cuerpo["pageToken"] = token
        d = await llamar("POST", f"customers/{_cid(cuenta)}/googleAds:search", cuerpo)
        filas.extend(d.get("results", []))
        token = d.get("nextPageToken")
        if not token or len(filas) >= limite:
            return filas[:limite]


def _texto_gaql(valor: str) -> str:
    return '"' + str(valor).replace("\\", "\\\\").replace('"', '\\"') + '"'


async def verificar_conexion() -> dict:
    """Lectura de prueba al arrancar: acceso válido, cuenta permitida y su moneda. Nunca devuelve tokens."""
    if not configurado():
        return {"ok": False, "detalle": "Sin configurar (faltan variables GOOGLE_ADS_*)"}
    if not config.GOOGLE_ADS_CUENTAS_PERMITIDAS:
        return {"ok": False, "detalle": "Falta GOOGLE_ADS_CUENTAS_PERMITIDAS"}
    cuenta = config.GOOGLE_ADS_CUENTAS_PERMITIDAS[0]
    try:
        filas = await buscar(cuenta, "SELECT customer.id, customer.descriptive_name, customer.currency_code, "
                                     "customer.time_zone FROM customer LIMIT 1")
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "version": config.GOOGLE_ADS_API_VERSION, "cuenta": cuenta, "detalle": str(e)[:400]}
    c = (filas[0] if filas else {}).get("customer", {})
    moneda_ok = c.get("currencyCode") == config.GOOGLE_ADS_MONEDA
    return {"ok": moneda_ok, "version": config.GOOGLE_ADS_API_VERSION, "cuenta": c.get("descriptiveName") or cuenta,
            "moneda": c.get("currencyCode"), "zona_horaria": c.get("timeZone"),
            **({} if moneda_ok else {"detalle": f"La cuenta no está en {config.GOOGLE_ADS_MONEDA}"})}


# ------------------------------------------------------------------ validación
def _fecha(valor, campo: str, errores: list) -> date | None:
    try:
        return date.fromisoformat(str(valor))
    except Exception:
        errores.append(f"{campo}: fecha inválida (usa AAAA-MM-DD)")
        return None


def _validar_anuncio(a: dict, donde: str, errores: list) -> dict | None:
    titulos = [str(t).strip() for t in (a.get("titulos") or []) if str(t).strip()]
    descripciones = [str(t).strip() for t in (a.get("descripciones") or []) if str(t).strip()]
    url = str(a.get("url_final") or "").strip()
    if not TITULOS_MIN <= len(titulos) <= TITULOS_MAX:
        errores.append(f"{donde}: {len(titulos)} títulos; deben ser de {TITULOS_MIN} a {TITULOS_MAX}")
    if not DESCRIPCIONES_MIN <= len(descripciones) <= DESCRIPCIONES_MAX:
        errores.append(f"{donde}: {len(descripciones)} descripciones; deben ser de {DESCRIPCIONES_MIN} a {DESCRIPCIONES_MAX}")
    for i, t in enumerate(titulos, 1):
        if len(t) > TITULO_LARGO:
            errores.append(f"{donde}, título {i}: {len(t)} caracteres (máximo {TITULO_LARGO}): «{t}»")
    for i, t in enumerate(descripciones, 1):
        if len(t) > DESCRIPCION_LARGO:
            errores.append(f"{donde}, descripción {i}: {len(t)} caracteres (máximo {DESCRIPCION_LARGO}): «{t}»")
    if len({t.lower() for t in titulos}) != len(titulos):
        errores.append(f"{donde}: hay títulos repetidos")
    if not url.startswith("https://"):
        errores.append(f"{donde}: la URL final debe empezar con https://")
    rutas = {}
    for campo in ("ruta1", "ruta2"):
        valor = str(a.get(campo) or "").strip().strip("/")
        if len(valor) > RUTA_LARGO:
            errores.append(f"{donde}, {campo}: {len(valor)} caracteres (máximo {RUTA_LARGO})")
        if valor:
            rutas["path1" if campo == "ruta1" else "path2"] = valor
    if rutas.get("path2") and not rutas.get("path1"):
        errores.append(f"{donde}: ruta2 sin ruta1")
    return {"finalUrls": [url], "responsiveSearchAd": {"headlines": [{"text": t} for t in titulos],
                                                        "descriptions": [{"text": t} for t in descripciones], **rutas}}


def _palabras(lista, donde: str, errores: list, negativa: bool = False) -> list[dict]:
    salida, vistas = [], set()
    if not isinstance(lista, (list, type(None))):
        errores.append(f"{donde}: debe ser una lista")
        return []
    for i, p in enumerate(lista or [], 1):
        if not isinstance(p, (str, dict)):
            errores.append(f"{donde}, palabra {i}: formato no válido")
            continue
        if isinstance(p, str):
            p = {"texto": p, "concordancia": "FRASE" if not negativa else "AMPLIA"}
        texto = str(p.get("texto", "")).strip()
        tipo = CONCORDANCIAS.get(str(p.get("concordancia", "FRASE")).strip().upper())
        if not texto:
            continue
        if tipo is None:
            errores.append(f"{donde}, palabra {i}: concordancia «{p.get('concordancia')}» no válida (EXACTA, FRASE o AMPLIA)")
            continue
        if len(texto) > PALABRA_LARGO or len(texto.split()) > PALABRA_MAX_PALABRAS:
            errores.append(f"{donde}, palabra {i}: máximo {PALABRA_LARGO} caracteres y {PALABRA_MAX_PALABRAS} palabras")
        if (texto.lower(), tipo) in vistas:
            continue
        vistas.add((texto.lower(), tipo))
        salida.append({"text": texto, "matchType": tipo})
    return salida


def armar_busqueda(spec: dict) -> tuple[list[str], list[dict], dict]:
    """Valida la campaña y arma las operaciones de googleAds:mutate (con IDs temporales negativos)."""
    errores: list[str] = []
    cid = _cid(spec.get("cuenta"))
    if not cuenta_permitida(cid):
        errores.append(f"Cuenta {spec.get('cuenta')} no permitida en este servidor")
    nombre = str(spec.get("nombre") or "").strip()
    if not nombre:
        errores.append("Falta el nombre de la campaña")
    presupuesto = numero_positivo(spec.get("presupuesto_diario_mxn")) or 0
    if presupuesto <= 0:
        errores.append("presupuesto_diario_mxn debe ser un número mayor a 0")
    tope = config.GOOGLE_ADS_PRESUPUESTO_MAX_DIARIO
    if tope and presupuesto > tope:
        errores.append(f"Presupuesto diario ${presupuesto:,.2f} arriba del tope del servidor (${tope:,.2f} MXN)")
    inicio = _fecha(spec.get("inicio"), "inicio", errores)
    fin = _fecha(spec.get("fin"), "fin", errores) if spec.get("fin") else None
    if inicio and inicio < date.today():
        errores.append("inicio: la fecha ya pasó")
    if inicio and fin and fin <= inicio:
        errores.append("fin: debe ser posterior al inicio")
    estrategia = str(spec.get("estrategia") or "MAXIMIZAR_CLICS").upper()
    cpc_max = spec.get("cpc_max_mxn")
    cpc_valor = numero_positivo(cpc_max) if cpc_max not in (None, "") else None
    if cpc_max not in (None, "") and cpc_valor is None:
        errores.append("cpc_max_mxn debe ser un número mayor a 0")
    if cpc_valor and tope and cpc_valor > tope:
        errores.append("cpc_max_mxn no puede ser mayor que el tope de presupuesto diario")
    cpc_micros = int(round(cpc_valor * 100)) * 10_000 if cpc_valor else None
    if estrategia not in ("MAXIMIZAR_CLICS", "CPC_MANUAL"):
        errores.append("estrategia: usa MAXIMIZAR_CLICS o CPC_MANUAL")
    if estrategia == "CPC_MANUAL" and not cpc_micros:
        errores.append("Con CPC_MANUAL hace falta cpc_max_mxn")
    ubicaciones = spec.get("ubicaciones") or [UBICACION_MEXICO]
    idiomas = spec.get("idiomas") or [IDIOMA_ESPANOL]
    for u in ubicaciones:
        if not re.fullmatch(r"geoTargetConstants/\d+", str(u)):
            errores.append(f"ubicación «{u}» no válida: usa geoTargetConstants/<id> (México = {UBICACION_MEXICO})")
    for i in idiomas:
        if not re.fullmatch(r"languageConstants/\d+", str(i)):
            errores.append(f"idioma «{i}» no válido: usa languageConstants/<id> (español = {IDIOMA_ESPANOL})")
    grupos = spec.get("grupos") or []
    if not isinstance(grupos, list) or not all(isinstance(g, dict) for g in grupos):
        errores.append("grupos debe ser una lista de objetos")
        grupos = []
    if not 1 <= len(grupos) <= MAX_GRUPOS:
        errores.append(f"Debe haber de 1 a {MAX_GRUPOS} grupos de anuncios")

    base = f"customers/{cid}"
    rn_presupuesto, rn_campana = f"{base}/campaignBudgets/-1", f"{base}/campaigns/-2"
    ops: list[dict] = [{"campaignBudgetOperation": {"create": {
        "resourceName": rn_presupuesto, "name": f"{nombre} · presupuesto",
        "amountMicros": str(int(round(presupuesto * 100)) * 10_000), "deliveryMethod": "STANDARD",
        "explicitlyShared": False}}}]
    campana = {
        "resourceName": rn_campana, "name": nombre, "status": "PAUSED", "advertisingChannelType": "SEARCH",
        "campaignBudget": rn_presupuesto,
        "networkSettings": {"targetGoogleSearch": True,
                            "targetSearchNetwork": bool(spec.get("red_de_socios_de_busqueda", False)),
                            "targetContentNetwork": bool(spec.get("red_display", False)),
                            "targetPartnerSearchNetwork": False},
        "geoTargetTypeSetting": {"positiveGeoTargetType": "PRESENCE"},
        "containsEuPoliticalAdvertising": "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING",
    }
    if inicio and inicio > date.today():  # si es hoy, Google arranca desde ahora (00:00 ya pasó)
        campana["startDateTime"] = f"{inicio.isoformat()} 00:00:00"
    if fin:
        campana["endDateTime"] = f"{fin.isoformat()} 23:59:59"
    if estrategia == "CPC_MANUAL":
        campana["manualCpc"] = {}
    else:
        campana["targetSpend"] = {"cpcBidCeilingMicros": str(cpc_micros)} if cpc_micros else {}
    ops.append({"campaignOperation": {"create": campana}})
    for u in ubicaciones:
        ops.append({"campaignCriterionOperation": {"create": {"campaign": rn_campana,
                                                              "location": {"geoTargetConstant": str(u)}}}})
    for i in idiomas:
        ops.append({"campaignCriterionOperation": {"create": {"campaign": rn_campana,
                                                              "language": {"languageConstant": str(i)}}}})
    for kw in _palabras(spec.get("negativas_campana"), "negativas de campaña", errores, negativa=True):
        ops.append({"campaignCriterionOperation": {"create": {"campaign": rn_campana, "negative": True, "keyword": kw}}})

    total_anuncios = 0
    for g_i, g in enumerate(grupos, 1):
        donde = f"grupo {g_i} «{g.get('nombre', '')}»"
        rn_grupo = f"{base}/adGroups/{-2 - g_i}"
        grupo = {"resourceName": rn_grupo, "campaign": rn_campana, "name": str(g.get("nombre") or f"Grupo {g_i}"),
                 "status": "ENABLED", "type": "SEARCH_STANDARD"}
        if estrategia == "CPC_MANUAL" and cpc_micros:
            grupo["cpcBidMicros"] = str(cpc_micros)
        ops.append({"adGroupOperation": {"create": grupo}})
        palabras = _palabras(g.get("palabras_clave"), donde, errores)
        if not palabras:
            errores.append(f"{donde}: no tiene palabras clave")
        for kw in palabras:
            ops.append({"adGroupCriterionOperation": {"create": {"adGroup": rn_grupo, "status": "ENABLED", "keyword": kw}}})
        for kw in _palabras(g.get("negativas"), f"{donde} (negativas)", errores, negativa=True):
            ops.append({"adGroupCriterionOperation": {"create": {"adGroup": rn_grupo, "negative": True, "keyword": kw}}})
        anuncios = g.get("anuncios") or []
        if not isinstance(anuncios, list) or not all(isinstance(x, dict) for x in anuncios):
            errores.append(f"{donde}: anuncios debe ser una lista de objetos")
            anuncios = []
        if not 1 <= len(anuncios) <= MAX_ANUNCIOS_POR_GRUPO:
            errores.append(f"{donde}: debe tener de 1 a {MAX_ANUNCIOS_POR_GRUPO} anuncios")
        for a_i, a in enumerate(anuncios, 1):
            anuncio = _validar_anuncio(a, f"{donde}, anuncio {a_i}", errores)
            ops.append({"adGroupAdOperation": {"create": {"adGroup": rn_grupo, "status": "ENABLED", "ad": anuncio}}})
            total_anuncios += 1
    resumen = {"cuenta": cid, "nombre": nombre, "presupuesto_diario_mxn": presupuesto, "estrategia": estrategia,
               "inicio": spec.get("inicio"), "fin": spec.get("fin"), "grupos": len(grupos), "anuncios": total_anuncios,
               "operaciones": len(ops), "estatus_campana": "PAUSED"}
    return errores, ops, resumen


def _resultados(respuesta: dict) -> dict:
    salida: dict[str, list[str]] = {}
    for r in respuesta.get("mutateOperationResponses", []) or []:
        for clave, valor in r.items():
            if isinstance(valor, dict) and valor.get("resourceName"):
                salida.setdefault(clave.replace("Result", ""), []).append(valor["resourceName"])
    return salida


# ------------------------------------------------------------------ herramientas
def crear_servidor(ctx: Contexto):
    def registrar(accion: str, detalle: str):
        ctx.escrituras.append(f"{accion}: {detalle}")
        db.evento(ctx.conv_id, "operador-pauta", accion, detalle)

    async def mutar(cid: str, ops: list[dict], que: str) -> dict:
        validar = config.MODO_PRUEBA
        if validar and not configurado():
            registrar(f"simulado:{que}", f"{len(ops)} operaciones")
            return {"modo_prueba": True, "validado_por_google": False,
                    "nota": "MODO_PRUEBA y Google Ads sin configurar: no se envió nada.", "operaciones": ops}
        d = await llamar("POST", f"customers/{cid}/googleAds:mutate",
                         {"mutateOperations": ops, "validateOnly": validar})
        if validar:
            registrar(f"validado:{que}", f"{len(ops)} operaciones aceptadas por Google sin crear nada")
            return {"modo_prueba": True, "validado_por_google": True,
                    "nota": "MODO_PRUEBA: Google validó todas las operaciones y no creó nada."}
        creados = _resultados(d)
        registrar(que, json.dumps(creados, ensure_ascii=False)[:500])
        return {"creado": creados}

    @tool("google_ads_consultar",
          "Lee datos de Google Ads con una consulta GAQL (solo SELECT). Sirve para revisar campañas, grupos, "
          "anuncios, palabras clave, métricas por fecha y buscar IDs de ubicaciones (geo_target_constant) o "
          "idiomas (language_constant). 'cuenta' es el ID de cliente sin guiones.",
          esquema({"cuenta": {"type": "string"}, "gaql": {"type": "string"},
                   "limite": {"type": "integer", "default": 500}}, ["cuenta", "gaql"]))
    async def google_ads_consultar(a):
        cid = _cid(a["cuenta"])
        if not cuenta_permitida(cid):
            return error("BLOQUEADO: cuenta de Google Ads no permitida en este servidor.")
        gaql = str(a["gaql"]).strip()
        if not gaql.upper().startswith("SELECT ") or ";" in gaql:
            return error("Solo se permiten consultas GAQL que empiecen con SELECT (una sola consulta).")
        try:
            filas = await buscar(cid, gaql, max(1, min(int(a.get("limite") or 500), 5000)))
            return ok({"filas": len(filas), "resultados": filas})
        except Exception as e:  # noqa: BLE001
            return error(f"ERROR DE GOOGLE ADS: {e}")

    @tool("google_ads_montar_busqueda",
          "Crea una campaña de la Red de Búsqueda completa EN PAUSA en una sola operación atómica: presupuesto "
          "diario, campaña, ubicaciones, idiomas, negativas, grupos, palabras clave y anuncios responsivos. Si Google "
          "rechaza cualquier pieza, no se crea nada. 'campana_json' sigue el formato de la skill campana-google. "
          "Revisa antes que no exista una campaña con el mismo nombre. Requiere aprobación humana vigente.",
          esquema({"campana_json": {"type": "string"}}, ["campana_json"]))
    async def google_ads_montar_busqueda(a):
        permitido, motivo = ctx.puede_escribir()
        if not permitido:
            return error(motivo)
        try:
            spec = cargar_json(a["campana_json"], {})
        except Exception as e:  # noqa: BLE001
            return error(f"campana_json no es JSON válido: {e}")
        if not isinstance(spec, dict):
            return error("campana_json debe ser un objeto JSON")
        errores, ops, resumen = armar_busqueda(spec)
        if errores:
            return error("No monté nada. Corrige esto:\n- " + "\n- ".join(errores))
        cid = resumen["cuenta"]
        try:
            if configurado():
                cliente = await buscar(cid, "SELECT customer.currency_code FROM customer LIMIT 1", 1)
                moneda = ((cliente[0] if cliente else {}).get("customer") or {}).get("currencyCode")
                if moneda != config.GOOGLE_ADS_MONEDA:
                    return error(f"BLOQUEADO: la cuenta está en {moneda}, no en {config.GOOGLE_ADS_MONEDA}; "
                                 "el presupuesto del brief no se puede convertir.")
                previas = await buscar(cid, "SELECT campaign.id, campaign.status FROM campaign WHERE campaign.name = "
                                            f"{_texto_gaql(resumen['nombre'])} AND campaign.status != 'REMOVED'", 5)
                if previas:
                    return error(f"Ya existe una campaña con ese nombre (ID {previas[0]['campaign']['id']}). No monté nada.")
            resultado = await mutar(cid, ops, "campaña de búsqueda")
        except Exception as e:  # noqa: BLE001
            return error(f"ERROR DE GOOGLE ADS (no se creó nada, la operación es atómica): {e}")
        if resultado.get("creado"):
            camp = (resultado["creado"].get("campaign") or [""])[0]
            resumen["campana_id"] = camp.rsplit("/", 1)[-1] if camp else ""
            resumen["link"] = (f"https://ads.google.com/aw/campaigns?campaignId={resumen['campana_id']}"
                               if camp else "")
        return ok({**resumen, **resultado})

    @tool("google_ads_agregar_anuncio",
          "Agrega un anuncio responsivo de búsqueda NUEVO, EN PAUSA, a un grupo de anuncios existente (los anuncios "
          "de Google no se editan: para cambiar texto se crea uno nuevo y se pausa el anterior con google_ads_pausar). "
          "'grupo' es el ID numérico del grupo de anuncios. Requiere aprobación humana vigente.",
          esquema({"cuenta": {"type": "string"}, "grupo": {"type": "string"},
                   "anuncio_json": {"type": "string", "description": "{titulos[], descripciones[], url_final, ruta1, ruta2}"}},
                  ["cuenta", "grupo", "anuncio_json"]))
    async def google_ads_agregar_anuncio(a):
        permitido, motivo = ctx.puede_escribir()
        if not permitido:
            return error(motivo)
        cid, grupo = _cid(a["cuenta"]), _cid(a["grupo"])
        if not cuenta_permitida(cid):
            return error("BLOQUEADO: cuenta de Google Ads no permitida en este servidor.")
        if not grupo:
            return error("grupo: falta el ID numérico del grupo de anuncios.")
        try:
            datos_anuncio = cargar_json(a["anuncio_json"], {})
        except Exception as e:  # noqa: BLE001
            return error(f"anuncio_json no es JSON válido: {e}")
        if not isinstance(datos_anuncio, dict):
            return error("anuncio_json debe ser un objeto JSON")
        errores: list[str] = []
        anuncio = _validar_anuncio(datos_anuncio, "anuncio", errores)
        if errores:
            return error("No agregué nada. Corrige esto:\n- " + "\n- ".join(errores))
        op = {"adGroupAdOperation": {"create": {"adGroup": f"customers/{cid}/adGroups/{grupo}",
                                                "status": "PAUSED", "ad": anuncio}}}
        try:
            return ok(await mutar(cid, [op], f"anuncio nuevo en pausa en grupo {grupo}"))
        except Exception as e:  # noqa: BLE001
            return error(f"ERROR DE GOOGLE ADS: {e}")

    @tool("google_ads_agregar_palabras",
          "Agrega palabras clave (EN PAUSA) o negativas a un grupo de anuncios existente. Cada palabra: "
          "{texto, concordancia: EXACTA|FRASE|AMPLIA}. Requiere aprobación humana vigente.",
          esquema({"cuenta": {"type": "string"}, "grupo": {"type": "string"},
                   "palabras_json": {"type": "string"}, "negativas_json": {"type": "string"}},
                  ["cuenta", "grupo"]))
    async def google_ads_agregar_palabras(a):
        permitido, motivo = ctx.puede_escribir()
        if not permitido:
            return error(motivo)
        cid, grupo = _cid(a["cuenta"]), _cid(a["grupo"])
        if not cuenta_permitida(cid):
            return error("BLOQUEADO: cuenta de Google Ads no permitida en este servidor.")
        if not grupo:
            return error("grupo: falta el ID numérico del grupo de anuncios.")
        try:
            positivas = cargar_json(a.get("palabras_json"), [])
            negativas = cargar_json(a.get("negativas_json"), [])
        except Exception as e:  # noqa: BLE001
            return error(f"palabras_json o negativas_json no son JSON válido: {e}")
        errores: list[str] = []
        rn = f"customers/{cid}/adGroups/{grupo}"
        ops = [{"adGroupCriterionOperation": {"create": {"adGroup": rn, "status": "PAUSED", "keyword": kw}}}
               for kw in _palabras(positivas, "palabras", errores)]
        ops += [{"adGroupCriterionOperation": {"create": {"adGroup": rn, "negative": True, "keyword": kw}}}
                for kw in _palabras(negativas, "negativas", errores, negativa=True)]
        if errores or not ops:
            return error("No agregué nada. " + ("Corrige esto:\n- " + "\n- ".join(errores) if errores else "No hay palabras."))
        try:
            return ok(await mutar(cid, ops, f"{len(ops)} palabras en grupo {grupo}"))
        except Exception as e:  # noqa: BLE001
            return error(f"ERROR DE GOOGLE ADS: {e}")

    @tool("google_ads_pausar",
          "Pausa una campaña, grupo, anuncio o palabra clave por su resource name "
          "(customers/<id>/campaigns/<id>, adGroups/<id>, adGroupAds/<grupo>~<anuncio>, adGroupCriteria/<grupo>~<id>). "
          "Es lo único que cambia estatus: no existe forma de activar. Requiere aprobación humana vigente.",
          esquema({"recurso": {"type": "string"}}, ["recurso"]))
    async def google_ads_pausar(a):
        permitido, motivo = ctx.puede_escribir()
        if not permitido:
            return error(motivo)
        recurso = str(a["recurso"]).strip()
        m = RECURSO_PAUSABLE.match(recurso)
        if not m:
            return error("Recurso no válido. Ejemplo: customers/3701698329/campaigns/123456789")
        if not cuenta_permitida(m.group(1)):
            return error("BLOQUEADO: cuenta de Google Ads no permitida en este servidor.")
        op = {OPERACION_POR_RECURSO[m.group(2)]: {"update": {"resourceName": recurso, "status": "PAUSED"},
                                                  "updateMask": "status"}}
        try:
            return ok(await mutar(m.group(1), [op], f"pausar {recurso}"))
        except Exception as e:  # noqa: BLE001
            return error(f"ERROR DE GOOGLE ADS: {e}")

    herramientas = [google_ads_consultar, google_ads_montar_busqueda, google_ads_agregar_anuncio,
                    google_ads_agregar_palabras, google_ads_pausar]
    return create_sdk_mcp_server(name="google_ads", version="1.0.0", tools=herramientas), herramientas
