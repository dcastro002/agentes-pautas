"""Herramientas de LinkedIn Ads (API de Marketing, REST versionada) con candados.

Candados en código, no en instrucciones:
- Grupo de campañas, campaña y creativos se crean siempre en DRAFT (LinkedIn: "no elegible para
  mostrarse"). No existe ninguna herramienta para activar: cambiar estatus solo acepta PAUSED o ARCHIVED.
- Los posts de los anuncios son "ocultos" (feedDistribution NONE): no salen en el feed de la página.
- Si el montaje falla a la mitad, se borran el grupo y la campaña que quedaron en DRAFT (LinkedIn
  permite borrar lo que está en DRAFT). Los posts ocultos no se ven en ningún lado y se reportan.
- Solo cuentas de LINKEDIN_CUENTAS_PERMITIDAS, moneda verificada y presupuesto bajo el tope.
- Toda escritura exige aprobación humana vigente (ctx.aprobado).
- En MODO_PRUEBA solo se leen datos reales (la cuenta); las escrituras se simulan.
"""
import asyncio
import json
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
from claude_agent_sdk import create_sdk_mcp_server, tool

from .. import config, db
from ..contexto import Contexto
from urllib.parse import unquote

from .comun import cargar_json, descargar_imagen, error, esquema, numero_positivo, ok

API = "https://api.linkedin.com/rest"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
ZONA_CDMX = timezone(timedelta(hours=-6))

OBJETIVOS = {"VISITAS_SITIO": "WEBSITE_VISIT", "WEBSITE_VISIT": "WEBSITE_VISIT",
             "INTERACCION": "ENGAGEMENT", "ENGAGEMENT": "ENGAGEMENT",
             "RECONOCIMIENTO": "BRAND_AWARENESS", "BRAND_AWARENESS": "BRAND_AWARENESS"}
CTAS = {"LEARN_MORE", "SIGN_UP", "REGISTER", "DOWNLOAD", "SUBSCRIBE", "REQUEST_DEMO", "SEE_MORE", "APPLY",
        "JOIN", "ATTEND", "VIEW_QUOTE"}
FACETAS = {"ubicaciones": "locations", "cargos": "titles", "funciones": "jobFunctions",
           "seniority": "seniorities", "industrias": "industries", "tamano_empresa": "staffCountRanges",
           "habilidades": "skills", "empresas": "employers", "idiomas_interfaz": "interfaceLocales"}
TEXTO_MAX, TEXTO_RECOMENDADO = 600, 150
TITULO_MAX, TITULO_RECOMENDADO = 200, 70
MAX_ANUNCIOS = 10
RECURSOS = {"grupo": "adCampaignGroups", "campana": "adCampaigns", "creativo": "creatives"}
# Rutas de lectura permitidas (la cuenta se valida aparte); nada de ".." ni rutas libres
RUTA_CUENTA = re.compile(r"^adAccounts/(\d+)(?:/(?:adCampaigns|adCampaignGroups)(?:/\d+)?"
                         r"|/creatives(?:/urn%3Ali%3AsponsoredCreative%3A\d+)?)?$")
RUTAS_SIN_CUENTA = {"adTargetingEntities", "adTargetingFacets", "audienceCounts"}
RUTAS_CON_CUENTA_EN_CONSULTA = {"adAnalytics", "adBudgetPricing"}
FILTROS_PROHIBIDOS = ("campaigns=", "campaigngroups=", "creatives=", "companies=", "shares=", "share=")
ESPECIALES_TEXTO = "\\|{}@[]()<>#*_~"


def escapar_texto(texto: str) -> str:
    """El texto de un post usa el formato 'little' de LinkedIn: estos caracteres van escapados."""
    return "".join("\\" + ch if ch in ESPECIALES_TEXTO else ch for ch in texto)


def _decodificar(texto: str) -> str:
    anterior, actual = None, texto or ""
    for _ in range(5):
        if actual == anterior:
            break
        anterior, actual = actual, unquote(actual)
    return actual

_token: dict = {"valor": None, "vence": 0.0}


class ErrorLinkedIn(RuntimeError):
    pass


# ------------------------------------------------------------------ conexión
def configurado() -> bool:
    return bool(config.LINKEDIN_ACCESS_TOKEN or (config.LINKEDIN_REFRESH_TOKEN and config.LINKEDIN_CLIENT_ID
                                                  and config.LINKEDIN_CLIENT_SECRET))


def _id(valor) -> str:
    return re.sub(r"\D", "", str(valor or "").rsplit(":", 1)[-1])


def cuenta_permitida(cuenta) -> bool:
    return bool(config.LINKEDIN_CUENTAS_PERMITIDAS) and _id(cuenta) in config.LINKEDIN_CUENTAS_PERMITIDAS


async def _access_token() -> str:
    if config.LINKEDIN_REFRESH_TOKEN and config.LINKEDIN_CLIENT_ID and config.LINKEDIN_CLIENT_SECRET:
        if _token["valor"] and time.time() < _token["vence"] - 300:
            return _token["valor"]
        async with httpx.AsyncClient(timeout=30) as cli:
            r = await cli.post(TOKEN_URL, data={"grant_type": "refresh_token",
                                                "refresh_token": config.LINKEDIN_REFRESH_TOKEN,
                                                "client_id": config.LINKEDIN_CLIENT_ID,
                                                "client_secret": config.LINKEDIN_CLIENT_SECRET})
        cuerpo = r.json() if r.content else {}
        if r.status_code < 400 and cuerpo.get("access_token"):
            _token.update(valor=cuerpo["access_token"], vence=time.time() + int(cuerpo.get("expires_in", 3600)))
            return _token["valor"]
        if not config.LINKEDIN_ACCESS_TOKEN:
            raise ErrorLinkedIn(f"No pude renovar el acceso a LinkedIn ({cuerpo.get('error', r.status_code)}).")
    if not config.LINKEDIN_ACCESS_TOKEN:
        raise ErrorLinkedIn("LinkedIn no está configurado en el servidor (falta LINKEDIN_ACCESS_TOKEN).")
    return config.LINKEDIN_ACCESS_TOKEN


async def _encabezados(extra: dict | None = None) -> dict:
    return {"Authorization": f"Bearer {await _access_token()}", "LinkedIn-Version": config.LINKEDIN_API_VERSION,
            "X-Restli-Protocol-Version": "2.0.0", **(extra or {})}


def _formatear_error(r: httpx.Response) -> str:
    try:
        c = r.json()
    except Exception:
        return f"HTTP {r.status_code}: {r.text[:300]}"
    partes = [f"HTTP {r.status_code}", str(c.get("message", ""))[:400], str(c.get("code", "") or "")]
    for e in (c.get("errorDetails") or {}).get("inputErrors", []) or []:
        campo = ((e.get("input") or {}).get("inputPath") or {}).get("fieldPath", "")
        partes.append(f"· {e.get('code', '')}: {e.get('description', '')}" + (f" (campo: {campo})" if campo else ""))
    if c.get("serviceErrorCode") == 65601 or r.status_code == 401:
        partes.append("· El token de LinkedIn venció o no es válido: genera uno nuevo y actualiza LINKEDIN_ACCESS_TOKEN.")
    return " ".join(p for p in partes if p)


async def llamar(metodo: str, ruta: str, cuerpo: dict | None = None, consulta: str = "",
                 extra: dict | None = None) -> tuple[dict, dict]:
    """Devuelve (cuerpo JSON, encabezados). La ruta es relativa a /rest."""
    url = f"{API}/{ruta.lstrip('/')}" + (f"?{consulta.lstrip('?')}" if consulta else "")
    async with httpx.AsyncClient(timeout=120) as cli:
        r = await cli.request(metodo, url, headers=await _encabezados(extra), json=cuerpo)
    if r.status_code >= 400:
        raise ErrorLinkedIn(_formatear_error(r))
    try:
        datos = r.json() if r.content else {}
    except Exception:
        datos = {}
    return datos, dict(r.headers)


def _id_creado(encabezados: dict) -> str:
    return encabezados.get("x-restli-id") or encabezados.get("X-RestLi-Id") or ""


async def cuenta(cuenta_id: str) -> dict:
    datos, _ = await llamar("GET", f"adAccounts/{_id(cuenta_id)}")
    return datos


async def verificar_conexion() -> dict:
    if not configurado():
        return {"ok": False, "detalle": "Sin configurar (falta LINKEDIN_ACCESS_TOKEN)"}
    if not config.LINKEDIN_CUENTAS_PERMITIDAS:
        return {"ok": False, "detalle": "Falta LINKEDIN_CUENTAS_PERMITIDAS"}
    cid = config.LINKEDIN_CUENTAS_PERMITIDAS[0]
    try:
        c = await cuenta(cid)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "version": config.LINKEDIN_API_VERSION, "cuenta": cid, "detalle": str(e)[:400]}
    moneda_ok = c.get("currency") == config.LINKEDIN_MONEDA
    return {"ok": moneda_ok and c.get("status") in ("ACTIVE", None), "version": config.LINKEDIN_API_VERSION,
            "cuenta": c.get("name") or cid, "moneda": c.get("currency"), "estatus": c.get("status"),
            "organizacion": c.get("reference"),
            **({} if moneda_ok else {"detalle": f"La cuenta no está en {config.LINKEDIN_MONEDA}"})}


# ------------------------------------------------------------------ validación
def _epoch_ms(dia: date, fin: bool = False) -> int:
    momento = datetime.combine(dia + timedelta(days=1) if fin else dia, datetime.min.time(), ZONA_CDMX)
    return int(momento.timestamp() * 1000)


def _monto(valor) -> float:
    return numero_positivo(valor) or 0.0


def _segmentacion(seg: dict, errores: list) -> dict:
    def grupos(bloque: dict, donde: str) -> list[dict]:
        salida = []
        for clave, valores in (bloque or {}).items():
            if clave == "excluir":
                continue
            faceta = FACETAS.get(clave)
            if not faceta:
                errores.append(f"segmentación: «{clave}» no es una faceta soportada ({', '.join(FACETAS)})")
                continue
            urns = [str(v).strip() for v in (valores or []) if str(v).strip()]
            malos = [u for u in urns if not u.startswith("urn:li:")]
            if malos:
                errores.append(f"segmentación {donde}, {clave}: usa URNs de LinkedIn (urn:li:…), no texto: {malos[:3]}")
            if urns:
                salida.append({"or": {f"urn:li:adTargetingFacet:{faceta}": urns}})
        return salida

    incluir = grupos(seg, "incluir")
    if not any("urn:li:adTargetingFacet:locations" in g["or"] for g in incluir):
        errores.append("segmentación: falta al menos una ubicación (urn:li:geo:…)")
    criterio: dict = {"include": {"and": incluir}}
    excluir = grupos(seg.get("excluir") or {}, "excluir")
    if excluir:
        juntos: dict = {}
        for g in excluir:
            juntos.update(g["or"])
        criterio["exclude"] = {"or": juntos}
    return criterio


def validar_anuncio(a: dict, donde: str, errores: list, avisos: list) -> dict:
    texto = str(a.get("texto") or "").strip()
    titulo = str(a.get("titulo") or "").strip()
    url = str(a.get("url") or "").strip()
    cta = str(a.get("cta") or "LEARN_MORE").strip().upper()
    if not texto:
        errores.append(f"{donde}: falta el texto (introductorio)")
    elif len(texto) > TEXTO_MAX:
        errores.append(f"{donde}: texto de {len(texto)} caracteres (máximo {TEXTO_MAX})")
    elif len(texto) > TEXTO_RECOMENDADO:
        avisos.append(f"{donde}: el texto tiene {len(texto)} caracteres; LinkedIn corta después de ~{TEXTO_RECOMENDADO} con «ver más»")
    if not titulo:
        errores.append(f"{donde}: falta el título")
    elif len(titulo) > TITULO_MAX:
        errores.append(f"{donde}: título de {len(titulo)} caracteres (máximo {TITULO_MAX})")
    elif len(titulo) > TITULO_RECOMENDADO:
        avisos.append(f"{donde}: el título tiene {len(titulo)} caracteres; se recomienda hasta {TITULO_RECOMENDADO}")
    if not url.startswith("https://"):
        errores.append(f"{donde}: la URL debe empezar con https://")
    if cta not in CTAS:
        errores.append(f"{donde}: CTA «{cta}» no válido ({', '.join(sorted(CTAS))})")
    if not str(a.get("imagen") or "").strip():
        errores.append(f"{donde}: falta la imagen (public_url de Monday o ruta del PNG)")
    return {"texto": texto, "titulo": titulo, "url": url, "cta": cta, "imagen": str(a.get("imagen") or "").strip(),
            "nombre_archivo": a.get("nombre_archivo")}


def armar_campana(spec: dict) -> tuple[list[str], list[str], dict]:
    """Valida la campaña y arma los cuerpos de grupo y campaña (los anuncios se arman al montar)."""
    errores: list[str] = []
    avisos: list[str] = []
    cid = _id(spec.get("cuenta"))
    if not cuenta_permitida(cid):
        errores.append(f"Cuenta {spec.get('cuenta')} no permitida en este servidor")
    nombre = str(spec.get("nombre") or "").strip()
    if not nombre:
        errores.append("Falta el nombre de la campaña")
    elif len(nombre.encode()) > 200:
        errores.append("El nombre pasa de 200 bytes")
    objetivo = OBJETIVOS.get(str(spec.get("objetivo") or "VISITAS_SITIO").upper())
    if not objetivo:
        errores.append("objetivo: VISITAS_SITIO, INTERACCION o RECONOCIMIENTO")
    presupuesto = _monto(spec.get("presupuesto_diario"))
    if presupuesto <= 0:
        errores.append("presupuesto_diario debe ser mayor a 0")
    tope = config.LINKEDIN_PRESUPUESTO_MAX_DIARIO
    if tope and presupuesto > tope:
        errores.append(f"Presupuesto diario {presupuesto:,.2f} arriba del tope del servidor ({tope:,.2f} {config.LINKEDIN_MONEDA})")
    puja = spec.get("puja") or {}
    tipo_puja = str(puja.get("tipo") or "CPC").upper()
    monto_puja = _monto(puja.get("monto"))
    if tipo_puja not in ("CPC", "CPM"):
        errores.append("puja.tipo: CPC o CPM")
    if monto_puja <= 0:
        errores.append("puja.monto: falta la puja (consulta la sugerida con adBudgetPricing)")
    try:
        inicio = date.fromisoformat(str(spec.get("inicio")))
        if inicio < date.today():
            errores.append("inicio: la fecha ya pasó")
    except ValueError:
        inicio = None
        errores.append("inicio: fecha inválida (AAAA-MM-DD)")
    fin = None
    if spec.get("fin"):
        try:
            fin = date.fromisoformat(str(spec["fin"]))
            if inicio and fin <= inicio:
                errores.append("fin: debe ser posterior al inicio")
        except ValueError:
            errores.append("fin: fecha inválida (AAAA-MM-DD)")
    if objetivo == "WEBSITE_VISIT" and tipo_puja == "CPM":
        avisos.append("Visitas al sitio suele pujarse por CPC")
    if tope and monto_puja > tope:
        errores.append("puja.monto no puede ser mayor que el tope de presupuesto diario")
    segmentacion = spec.get("segmentacion") or {}
    if not isinstance(segmentacion, dict):
        errores.append("segmentacion debe ser un objeto")
        segmentacion = {}
    criterio = _segmentacion(segmentacion, errores)
    anuncios = spec.get("anuncios") or []
    if not isinstance(anuncios, list) or not all(isinstance(x, dict) for x in anuncios):
        errores.append("anuncios debe ser una lista de objetos")
        anuncios = []
    if not 1 <= len(anuncios) <= MAX_ANUNCIOS:
        errores.append(f"Debe haber de 1 a {MAX_ANUNCIOS} anuncios")
    anuncios_ok = [validar_anuncio(a, f"anuncio {i}", errores, avisos) for i, a in enumerate(anuncios, 1)]

    moneda = config.LINKEDIN_MONEDA
    cuenta_urn = f"urn:li:sponsoredAccount:{cid}"
    horario = {"start": _epoch_ms(inicio)} if inicio else {}
    if fin:
        horario["end"] = _epoch_ms(fin, fin=True)
    grupo = {"account": cuenta_urn, "name": nombre, "status": "DRAFT", "runSchedule": horario}
    campana = {
        "account": cuenta_urn, "name": nombre, "type": "SPONSORED_UPDATES", "objectiveType": objetivo,
        "costType": tipo_puja, "unitCost": {"amount": f"{monto_puja:.2f}", "currencyCode": moneda},
        "dailyBudget": {"amount": f"{presupuesto:.2f}", "currencyCode": moneda},
        "locale": {"country": str(spec.get("pais") or "MX").upper(), "language": str(spec.get("idioma") or "es").lower()},
        "offsiteDeliveryEnabled": bool(spec.get("red_de_audiencia", False)),
        "politicalIntent": "NOT_POLITICAL", "status": "DRAFT", "runSchedule": horario,
        "targetingCriteria": criterio,
    }
    plan = {"cuenta": cid, "nombre": nombre, "objetivo": objetivo, "presupuesto_diario": presupuesto,
            "moneda": moneda, "puja": f"{tipo_puja} {monto_puja:.2f}", "inicio": spec.get("inicio"),
            "fin": spec.get("fin"), "anuncios": len(anuncios_ok), "estatus": "DRAFT",
            "grupo": grupo, "campana": campana, "anuncios_detalle": anuncios_ok, "avisos": avisos}
    return errores, avisos, plan


def _ruta_local(ruta: str) -> Path | None:
    p = (config.AGENCIA_DIR / ruta).resolve() if not Path(ruta).is_absolute() else Path(ruta).resolve()
    raices = [config.AGENCIA_DIR.resolve(), config.ENTREGABLES_DIR.resolve()]
    return p if any(p == r or r in p.parents for r in raices) and p.is_file() else None


async def _leer_imagen(origen: str) -> bytes:
    if origen.startswith("https://"):
        return await descargar_imagen(origen, config.HOSTS_IMAGENES)
    ruta = _ruta_local(origen)
    if not ruta:
        raise ErrorLinkedIn(f"La imagen «{origen}» no existe o está fuera del proyecto.")
    return ruta.read_bytes()


# ------------------------------------------------------------------ herramientas
def crear_servidor(ctx: Contexto):
    def registrar(accion: str, detalle: str):
        ctx.escrituras.append(f"{accion}: {detalle}")
        db.evento(ctx.conv_id, "operador-pauta", accion, detalle)

    async def subir_imagen(organizacion: str, origen: str) -> str:
        contenido = await _leer_imagen(origen)
        datos, _ = await llamar("POST", "images", {"initializeUploadRequest": {"owner": organizacion}},
                                consulta="action=initializeUpload")
        valor = datos.get("value") or {}
        async with httpx.AsyncClient(timeout=120) as cli:
            r = await cli.put(valor["uploadUrl"], content=contenido,
                              headers={"Authorization": f"Bearer {await _access_token()}"})
        if r.status_code >= 400:
            raise ErrorLinkedIn(f"No pude subir la imagen: HTTP {r.status_code}")
        urn = valor["image"]
        for _ in range(15):  # hasta ~30 s: el post falla si la imagen sigue procesándose
            datos, _ = await llamar("GET", f"images/{urn.replace(':', '%3A')}")
            estado = datos.get("status")
            if estado == "AVAILABLE":
                return urn
            if estado == "PROCESSING_FAILED":
                raise ErrorLinkedIn("LinkedIn no pudo procesar la imagen (revisa formato y medidas).")
            await asyncio.sleep(2)
        raise ErrorLinkedIn("La imagen sigue procesándose en LinkedIn después de 30 s; vuelve a intentar.")

    async def crear_post(cid: str, organizacion: str, anuncio: dict, imagen_urn: str) -> str:
        cuerpo = {
            "author": organizacion, "commentary": escapar_texto(anuncio["texto"]), "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "NONE", "thirdPartyDistributionChannels": []},
            "content": {"media": {"id": imagen_urn, "title": anuncio["titulo"]}},
            "contentLandingPage": anuncio["url"], "contentCallToActionLabel": anuncio["cta"],
            "adContext": {"dscAdAccount": f"urn:li:sponsoredAccount:{cid}", "dscStatus": "ACTIVE"},
            "lifecycleState": "PUBLISHED", "isReshareDisabledByAuthor": True,
        }
        _, enc = await llamar("POST", "posts", cuerpo)
        return _id_creado(enc)

    async def crear_creativo(cid: str, campana_urn: str, post_urn: str, estatus: str) -> str:
        _, enc = await llamar("POST", f"adAccounts/{cid}/creatives",
                              {"content": {"reference": post_urn}, "campaign": campana_urn, "intendedStatus": estatus})
        return _id_creado(enc)

    async def contexto_cuenta(cid: str) -> tuple[str, str]:
        c = await cuenta(cid)
        if c.get("currency") != config.LINKEDIN_MONEDA:
            raise ErrorLinkedIn(f"BLOQUEADO: la cuenta está en {c.get('currency')}, no en {config.LINKEDIN_MONEDA}.")
        organizacion = c.get("reference") or ""
        if not organizacion.startswith("urn:li:organization:"):
            raise ErrorLinkedIn("La cuenta publicitaria no está ligada a una página de empresa (reference).")
        return organizacion, c.get("name", "")

    @tool("linkedin_consultar",
          "Lee datos de LinkedIn Ads (solo GET). 'ruta' es relativa a /rest, por ejemplo adAccounts/<id>, "
          "adAccounts/<id>/adCampaigns, adTargetingEntities, adTargetingFacets, adBudgetPricing, adAnalytics. "
          "'consulta' es el query string en formato Rest.li 2.0 (ej. q=typeahead&facet=urn%3Ali%3AadTargetingFacet%3Atitles&query=marketing). "
          "Úsalo para encontrar los URNs de segmentación (ubicaciones, cargos, seniority, industrias) y la puja sugerida.",
          esquema({"ruta": {"type": "string"}, "consulta": {"type": "string"}}, ["ruta"]))
    async def linkedin_consultar(a):
        ruta = str(a["ruta"]).strip().strip("/")
        consulta = str(a.get("consulta") or "")
        decodificada = _decodificar(consulta).lower()
        if ".." in _decodificar(ruta) or ".." in decodificada:
            return error("Ruta o consulta no válida.")
        m = RUTA_CUENTA.match(ruta)
        if m:
            if not cuenta_permitida(m.group(1)):
                return error("BLOQUEADO: cuenta de LinkedIn no permitida en este servidor.")
        elif ruta in RUTAS_CON_CUENTA_EN_CONSULTA:
            cuentas = re.findall(r"sponsoredaccount:(\d+)", decodificada)
            if not cuentas or not all(cuenta_permitida(c) for c in cuentas):
                return error("BLOQUEADO: la consulta debe nombrar solo cuentas permitidas (urn:li:sponsoredAccount:<id>).")
            if any(f in decodificada for f in FILTROS_PROHIBIDOS):
                return error("BLOQUEADO: filtra por cuenta (accounts= / account=), no por campañas, creativos ni empresas.")
        elif ruta not in RUTAS_SIN_CUENTA:
            return error("Ruta no permitida para consulta. Usa adAccounts/<id>[/adCampaigns|adCampaignGroups|creatives], "
                         "adTargetingEntities, adTargetingFacets, audienceCounts, adAnalytics o adBudgetPricing.")
        try:
            datos, _ = await llamar("GET", ruta, consulta=consulta)
            return ok(datos)
        except Exception as e:  # noqa: BLE001
            return error(f"ERROR DE LINKEDIN: {e}")

    @tool("linkedin_montar_campana",
          "Crea una campaña de LinkedIn completa EN BORRADOR (DRAFT): sube las imágenes, crea los posts ocultos "
          "(no salen en el feed), el grupo de campañas, la campaña con su segmentación y un creativo por anuncio. "
          "Si algo falla a la mitad, borra el grupo y la campaña en borrador. 'campana_json' sigue el formato de la "
          "skill campana-linkedin. Requiere aprobación humana vigente.",
          esquema({"campana_json": {"type": "string"}}, ["campana_json"]))
    async def linkedin_montar_campana(a):
        permitido, motivo = ctx.puede_escribir()
        if not permitido:
            return error(motivo)
        try:
            spec = cargar_json(a["campana_json"], {})
        except Exception as e:  # noqa: BLE001
            return error(f"campana_json no es JSON válido: {e}")
        if not isinstance(spec, dict):
            return error("campana_json debe ser un objeto JSON")
        errores, avisos, plan = armar_campana(spec)
        if errores:
            return error("No monté nada. Corrige esto:\n- " + "\n- ".join(errores))
        cid = plan["cuenta"]
        if config.MODO_PRUEBA:
            if configurado():
                try:
                    await contexto_cuenta(cid)
                except Exception as e:  # noqa: BLE001
                    return error(f"MODO_PRUEBA · la validación de la cuenta falló: {e}")
            registrar("simulado:linkedin", f"{plan['nombre']} · {plan['anuncios']} anuncios")
            return ok({"modo_prueba": True, "nota": "MODO_PRUEBA: no se envió nada a LinkedIn (no hay modo de solo "
                                                     "validar). Esto es lo que se crearía, todo en DRAFT.",
                       "se_enviaria": {k: plan[k] for k in ("grupo", "campana")},
                       "anuncios": plan["anuncios_detalle"], "avisos": avisos})
        creado: dict = {"imagenes": [], "posts": [], "creativos": []}
        grupo_id = campana_id = ""
        try:
            organizacion, _ = await contexto_cuenta(cid)
            for anuncio in plan["anuncios_detalle"]:
                imagen = await subir_imagen(organizacion, anuncio["imagen"])
                creado["imagenes"].append(imagen)
                creado["posts"].append(await crear_post(cid, organizacion, anuncio, imagen))
            plan["grupo"]["runSchedule"] = plan["campana"]["runSchedule"]
            _, enc = await llamar("POST", f"adAccounts/{cid}/adCampaignGroups", plan["grupo"])
            grupo_id = _id(_id_creado(enc))
            plan["campana"]["campaignGroup"] = f"urn:li:sponsoredCampaignGroup:{grupo_id}"
            _, enc = await llamar("POST", f"adAccounts/{cid}/adCampaigns", plan["campana"])
            campana_id = _id(_id_creado(enc))
            for post in creado["posts"]:
                creado["creativos"].append(await crear_creativo(cid, f"urn:li:sponsoredCampaign:{campana_id}", post, "DRAFT"))
        except Exception as e:  # noqa: BLE001
            limpieza = []
            pendientes = [("creatives", _id(c) and f"urn%3Ali%3AsponsoredCreative%3A{_id(c)}") for c in creado["creativos"]]
            pendientes += [("adCampaigns", campana_id), ("adCampaignGroups", grupo_id)]
            for recurso, rid in pendientes:
                if rid:
                    try:
                        await llamar("DELETE", f"adAccounts/{cid}/{recurso}/{rid}")
                        limpieza.append(f"borrado {recurso}/{rid} (estaba en DRAFT)")
                    except Exception as e2:  # noqa: BLE001
                        limpieza.append(f"NO se pudo borrar {recurso}/{rid}: {str(e2)[:150]}")
            registrar("linkedin:error", f"{str(e)[:300]} · {limpieza}")
            return error(f"ERROR DE LINKEDIN: {e}\nLimpieza: {limpieza or 'nada que limpiar'}\n"
                         f"Posts ocultos creados (no se ven en el feed): {creado['posts'] or 'ninguno'}")
        registrar("linkedin:campaña en DRAFT", json.dumps({"grupo": grupo_id, "campana": campana_id,
                                                          "creativos": creado["creativos"]})[:500])
        return ok({"creado": True, "estatus": "DRAFT", "grupo_id": grupo_id, "campana_id": campana_id,
                   "creativos": creado["creativos"], "posts": creado["posts"], "avisos": avisos,
                   "link": f"https://www.linkedin.com/campaignmanager/accounts/{cid}/campaigns",
                   "nota": "Todo quedó en borrador. Una persona revisa y lanza la campaña en Campaign Manager."})

    @tool("linkedin_agregar_anuncio",
          "Agrega un anuncio NUEVO a una campaña existente: sube la imagen, crea el post oculto y un creativo en "
          "DRAFT (no se muestra hasta que una persona lo active). En LinkedIn el contenido de un creativo no se "
          "edita: para cambiar arte o texto se crea uno nuevo y se pausa el anterior con linkedin_pausar. "
          "Requiere aprobación humana vigente.",
          esquema({"cuenta": {"type": "string"}, "campana_id": {"type": "string"},
                   "anuncio_json": {"type": "string", "description": "{texto, titulo, url, cta, imagen}"}},
                  ["cuenta", "campana_id", "anuncio_json"]))
    async def linkedin_agregar_anuncio(a):
        permitido, motivo = ctx.puede_escribir()
        if not permitido:
            return error(motivo)
        cid = _id(a["cuenta"])
        if not cuenta_permitida(cid):
            return error("BLOQUEADO: cuenta de LinkedIn no permitida en este servidor.")
        try:
            datos_anuncio = cargar_json(a["anuncio_json"], {})
        except Exception as e:  # noqa: BLE001
            return error(f"anuncio_json no es JSON válido: {e}")
        if not isinstance(datos_anuncio, dict) or not _id(a["campana_id"]):
            return error("anuncio_json debe ser un objeto JSON y campana_id un ID numérico")
        errores: list[str] = []
        avisos: list[str] = []
        anuncio = validar_anuncio(datos_anuncio, "anuncio", errores, avisos)
        if errores:
            return error("No agregué nada. Corrige esto:\n- " + "\n- ".join(errores))
        campana_urn = f"urn:li:sponsoredCampaign:{_id(a['campana_id'])}"
        if config.MODO_PRUEBA:
            registrar("simulado:linkedin anuncio", campana_urn)
            return ok({"modo_prueba": True, "nota": "MODO_PRUEBA: no se envió nada a LinkedIn.",
                       "se_crearia": {"campana": campana_urn, "anuncio": anuncio, "estatus": "DRAFT"}, "avisos": avisos})
        try:
            organizacion, _ = await contexto_cuenta(cid)
            datos, _ = await llamar("GET", f"adAccounts/{cid}/adCampaigns/{_id(a['campana_id'])}")
            if _id(datos.get("account")) != cid:
                return error("BLOQUEADO: la campaña no pertenece a esa cuenta.")
            imagen = await subir_imagen(organizacion, anuncio["imagen"])
            post = await crear_post(cid, organizacion, anuncio, imagen)
            creativo = await crear_creativo(cid, campana_urn, post, "DRAFT")
        except Exception as e:  # noqa: BLE001
            return error(f"ERROR DE LINKEDIN: {e}")
        registrar("linkedin:anuncio nuevo en DRAFT", f"{campana_urn} · {creativo}")
        return ok({"creativo": creativo, "post": post, "estatus": "DRAFT", "avisos": avisos,
                   "nota": "El anuncio nuevo quedó en borrador: una persona lo activa en Campaign Manager."})

    @tool("linkedin_pausar",
          "Pausa o archiva un grupo de campañas, una campaña o un creativo. Solo acepta PAUSED o ARCHIVED: no existe "
          "forma de activar. Requiere aprobación humana vigente.",
          esquema({"cuenta": {"type": "string"}, "tipo": {"type": "string", "enum": ["grupo", "campana", "creativo"]},
                   "id": {"type": "string"}, "estatus": {"type": "string", "enum": ["PAUSED", "ARCHIVED"]}},
                  ["cuenta", "tipo", "id", "estatus"]))
    async def linkedin_pausar(a):
        permitido, motivo = ctx.puede_escribir()
        if not permitido:
            return error(motivo)
        cid = _id(a["cuenta"])
        if not cuenta_permitida(cid):
            return error("BLOQUEADO: cuenta de LinkedIn no permitida en este servidor.")
        estatus = str(a["estatus"]).upper()
        if estatus not in ("PAUSED", "ARCHIVED"):
            return error("Solo se permite PAUSED o ARCHIVED.")
        recurso = RECURSOS.get(a["tipo"])
        if not recurso:
            return error("tipo: grupo, campana o creativo")
        rid = _id(a["id"])
        if not rid:
            return error("id no válido.")
        campo = "intendedStatus" if a["tipo"] == "creativo" else "status"
        # Los creativos se direccionan por URN codificado; grupos y campañas por ID numérico
        clave = f"urn%3Ali%3AsponsoredCreative%3A{rid}" if a["tipo"] == "creativo" else rid
        ruta = f"adAccounts/{cid}/{recurso}/{clave}"
        if config.MODO_PRUEBA:
            registrar("simulado:linkedin estatus", f"{ruta} → {estatus}")
            return ok({"modo_prueba": True, "nota": "MODO_PRUEBA: no se envió nada a LinkedIn.",
                       "se_enviaria": {"ruta": ruta, campo: estatus}})
        try:
            actual, _ = await llamar("GET", ruta)
            if a["tipo"] == "creativo":
                campana, _ = await llamar("GET", f"adAccounts/{cid}/adCampaigns/{_id(actual.get('campaign'))}")
                duena = _id(campana.get("account"))
            else:
                duena = _id(actual.get("account"))
            if duena != cid:
                return error("BLOQUEADO: ese elemento no pertenece a la cuenta permitida.")
            await llamar("POST", ruta, {"patch": {"$set": {campo: estatus}}}, extra={"X-RestLi-Method": "PARTIAL_UPDATE"})
        except Exception as e:  # noqa: BLE001
            return error(f"ERROR DE LINKEDIN: {e}")
        registrar(f"linkedin:{estatus}", ruta)
        return ok({"ok": True, "recurso": ruta, campo: estatus})

    herramientas = [linkedin_consultar, linkedin_montar_campana, linkedin_agregar_anuncio, linkedin_pausar]
    return create_sdk_mcp_server(name="linkedin", version="1.0.0", tools=herramientas), herramientas
