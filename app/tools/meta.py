"""Herramientas de Meta Ads (API de Marketing) con candados.

Candados en código, no en instrucciones:
- Nada se crea activo: campañas, conjuntos y anuncios se crean siempre en PAUSED.
- No existe ninguna herramienta para activar. Cambiar estatus solo acepta PAUSED o ARCHIVED.
- Solo cuentas publicitarias de META_CUENTAS_PERMITIDAS.
- Toda escritura exige aprobación humana vigente (ctx.aprobado).
- En MODO_PRUEBA las escrituras no se envían: se devuelve lo que se habría enviado.
"""
import itertools
import json
import re
from pathlib import Path

import httpx
from claude_agent_sdk import create_sdk_mcp_server, tool

from .. import config, db
from ..contexto import Contexto
from .comun import cargar_json, error, esquema, ok

_contador = itertools.count(1)
RUTA_VALIDA = re.compile(r"^(act_)?[0-9]+(/[a-z_]+)?$")
CTA_VALIDOS = ["LEARN_MORE", "SHOP_NOW", "SIGN_UP", "CONTACT_US", "MESSAGE_PAGE", "DOWNLOAD",
               "BOOK_NOW", "SUBSCRIBE", "REQUEST_TIME", "SEE_MORE", "APPLY_NOW", "GET_QUOTE"]


def _base() -> str:
    return f"https://graph.facebook.com/{config.META_API_VERSION}"


def _cuenta(cuenta: str) -> str:
    return str(cuenta).replace("act_", "").strip()


def _cuenta_permitida(cuenta: str) -> bool:
    return not config.META_CUENTAS_PERMITIDAS or _cuenta(cuenta) in config.META_CUENTAS_PERMITIDAS


async def _get(ruta: str, params: dict | None = None) -> dict:
    params = dict(params or {}, access_token=config.META_ACCESS_TOKEN)
    async with httpx.AsyncClient(timeout=90) as cli:
        r = await cli.get(f"{_base()}/{ruta}", params=params)
    return _respuesta(r)


async def _post(ruta: str, datos: dict, archivos: dict | None = None) -> dict:
    datos = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in datos.items() if v not in (None, "")}
    datos["access_token"] = config.META_ACCESS_TOKEN
    async with httpx.AsyncClient(timeout=120) as cli:
        r = await cli.post(f"{_base()}/{ruta}", data=datos, files=archivos)
    return _respuesta(r)


def _respuesta(r: httpx.Response) -> dict:
    try:
        cuerpo = r.json()
    except Exception:
        cuerpo = {"texto": r.text[:2000]}
    if r.status_code >= 400 or "error" in cuerpo:
        e = cuerpo.get("error", cuerpo)
        raise RuntimeError(json.dumps({k: e.get(k) for k in ("message", "type", "code", "error_subcode",
                                                             "error_user_title", "error_user_msg") if isinstance(e, dict)},
                                      ensure_ascii=False))
    return cuerpo


def _ruta_local(ruta: str) -> Path | None:
    """Solo archivos dentro del proyecto de la agencia o de los entregables."""
    p = (config.AGENCIA_DIR / ruta).resolve() if not Path(ruta).is_absolute() else Path(ruta).resolve()
    raices = [config.AGENCIA_DIR.resolve(), config.ENTREGABLES_DIR.resolve()]
    if any(p == r or r in p.parents for r in raices) and p.is_file():
        return p
    return None


def crear_servidor(ctx: Contexto):
    def registrar(accion: str, detalle: str):
        ctx.escrituras.append(f"{accion}: {detalle}")
        db.evento(ctx.conv_id, "operador-pauta", accion, detalle)

    def simulado(tipo: str, enviado: dict) -> dict:
        registrar(f"simulado:{tipo}", json.dumps(enviado, ensure_ascii=False)[:500])
        return ok({"modo_prueba": True, "id": f"PRUEBA-{tipo}-{next(_contador)}",
                   "nota": "MODO_PRUEBA activo: no se envió nada a Meta.", "se_enviaria": enviado})

    async def verificar_objeto(objeto_id: str) -> str | None:
        datos = await _get(objeto_id, {"fields": "account_id"})
        if not _cuenta_permitida(datos.get("account_id", "")):
            return f"BLOQUEADO: el objeto {objeto_id} pertenece a una cuenta no permitida."
        return None

    @tool("meta_consultar",
          "Lee datos de Meta (solo lectura): una cuenta (act_<id>), campaña, conjunto, anuncio, creativo o página, "
          "o un listado (ej. act_<id>/campaigns, <campaña>/ads, <anuncio>/insights). 'campos' son los fields de la API. "
          "'parametros_json' admite filtros como time_range, breakdowns, level, limit.",
          esquema({"ruta": {"type": "string"}, "campos": {"type": "string"},
                   "parametros_json": {"type": "string", "description": "JSON opcional con parámetros extra"}},
                  ["ruta", "campos"]))
    async def meta_consultar(a):
        ruta = a["ruta"].strip().strip("/")
        if not RUTA_VALIDA.match(ruta):
            return error("Ruta no válida. Usa un ID numérico, act_<id> o <id>/<listado>.")
        if ruta.startswith("act_") and not _cuenta_permitida(ruta.split("/")[0]):
            return error("BLOQUEADO: cuenta publicitaria no permitida en este servidor.")
        params = cargar_json(a.get("parametros_json"), {})
        params.pop("access_token", None)
        params["fields"] = a["campos"]
        try:
            datos = await _get(ruta, {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in params.items()})
            # Sigue la paginación hasta 1,000 filas
            filas = datos.get("data")
            siguiente = (datos.get("paging") or {}).get("next")
            while isinstance(filas, list) and siguiente and len(filas) < 1000:
                async with httpx.AsyncClient(timeout=90) as cli:
                    mas = _respuesta(await cli.get(siguiente))
                filas.extend(mas.get("data", []))
                siguiente = (mas.get("paging") or {}).get("next")
            if isinstance(filas, list):
                datos = {"data": filas, "filas": len(filas), "truncado": bool(siguiente)}
            return ok(datos)
        except Exception as e:
            return error(f"ERROR DE META: {e}")

    @tool("meta_crear_campana",
          "Crea una campaña EN PAUSA con presupuesto de campaña (CBO). Requiere aprobación humana vigente.",
          esquema({"cuenta": {"type": "string"}, "nombre": {"type": "string"},
                   "objetivo": {"type": "string", "enum": ["OUTCOME_LEADS", "OUTCOME_TRAFFIC", "OUTCOME_AWARENESS",
                                                            "OUTCOME_ENGAGEMENT", "OUTCOME_SALES"]},
                   "presupuesto_centavos": {"type": "integer", "minimum": 1},
                   "tipo_presupuesto": {"type": "string", "enum": ["diario", "total"]},
                   "categorias_especiales_json": {"type": "string", "description": "JSON, ej. [] o [\"HOUSING\"]"},
                   "pais_categoria": {"type": "string", "description": "Ej. MX, si hay categoría especial"},
                   "inicio": {"type": "string"}, "fin": {"type": "string"}},
                  ["cuenta", "nombre", "objetivo", "presupuesto_centavos", "tipo_presupuesto"]))
    async def meta_crear_campana(a):
        permitido, motivo = ctx.puede_escribir()
        if not permitido:
            return error(motivo)
        if not _cuenta_permitida(a["cuenta"]):
            return error("BLOQUEADO: cuenta publicitaria no permitida.")
        cats = cargar_json(a.get("categorias_especiales_json"), [])
        datos = {"name": a["nombre"], "objective": a["objetivo"], "status": "PAUSED",
                 "special_ad_categories": cats, "buying_type": "AUCTION",
                 "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
                 ("daily_budget" if a["tipo_presupuesto"] == "diario" else "lifetime_budget"): int(a["presupuesto_centavos"]),
                 "start_time": a.get("inicio"), "stop_time": a.get("fin")}
        if cats:
            datos["special_ad_category_country"] = [a.get("pais_categoria") or "MX"]
        if config.MODO_PRUEBA:
            return simulado("campana", datos)
        try:
            r = await _post(f"act_{_cuenta(a['cuenta'])}/campaigns", datos)
            registrar("campaña creada (pausa)", f"{r.get('id')} · {a['nombre']}")
            return ok({"id": r.get("id"), "estatus": "PAUSED"})
        except Exception as e:
            return error(f"ERROR DE META: {e}")

    @tool("meta_crear_conjunto",
          "Crea un conjunto de anuncios EN PAUSA dentro de una campaña. 'segmentacion_json' es el targeting de Meta "
          "(geo_locations, age_min, age_max, genders, publisher_platforms…). Requiere aprobación humana vigente.",
          esquema({"cuenta": {"type": "string"}, "campana_id": {"type": "string"}, "nombre": {"type": "string"},
                   "optimization_goal": {"type": "string"},
                   "billing_event": {"type": "string", "default": "IMPRESSIONS"},
                   "segmentacion_json": {"type": "string"},
                   "inicio": {"type": "string", "description": "ISO 8601 con zona, ej. 2026-10-27T00:00:00-0600"},
                   "fin": {"type": "string"},
                   "promoted_object_json": {"type": "string", "description": "JSON, ej. {\"pixel_id\":\"…\",\"custom_event_type\":\"LEAD\"}"},
                   "destination_type": {"type": "string"}},
                  ["cuenta", "campana_id", "nombre", "optimization_goal", "segmentacion_json", "inicio"]))
    async def meta_crear_conjunto(a):
        permitido, motivo = ctx.puede_escribir()
        if not permitido:
            return error(motivo)
        if not _cuenta_permitida(a["cuenta"]):
            return error("BLOQUEADO: cuenta publicitaria no permitida.")
        datos = {"name": a["nombre"], "campaign_id": a["campana_id"], "status": "PAUSED",
                 "optimization_goal": a["optimization_goal"], "billing_event": a.get("billing_event") or "IMPRESSIONS",
                 "targeting": cargar_json(a["segmentacion_json"], {}), "start_time": a["inicio"],
                 "end_time": a.get("fin"), "destination_type": a.get("destination_type")}
        po = cargar_json(a.get("promoted_object_json"), None)
        if po:
            datos["promoted_object"] = po
        if config.MODO_PRUEBA:
            return simulado("conjunto", datos)
        try:
            r = await _post(f"act_{_cuenta(a['cuenta'])}/adsets", datos)
            registrar("conjunto creado (pausa)", f"{r.get('id')} · {a['nombre']}")
            return ok({"id": r.get("id"), "estatus": "PAUSED"})
        except Exception as e:
            return error(f"ERROR DE META: {e}")

    @tool("meta_subir_imagen",
          "Sube una imagen a la biblioteca de la cuenta y devuelve su image_hash. 'origen' es una URL https "
          "(ej. la public_url de un archivo de Monday) o una ruta dentro del proyecto (ej. _Entregables/...png). "
          "Requiere aprobación humana vigente.",
          esquema({"cuenta": {"type": "string"}, "origen": {"type": "string"},
                   "nombre_archivo": {"type": "string"}}, ["cuenta", "origen"]))
    async def meta_subir_imagen(a):
        permitido, motivo = ctx.puede_escribir()
        if not permitido:
            return error(motivo)
        if not _cuenta_permitida(a["cuenta"]):
            return error("BLOQUEADO: cuenta publicitaria no permitida.")
        origen = a["origen"].strip()
        try:
            if origen.startswith("https://"):
                async with httpx.AsyncClient(timeout=120, follow_redirects=True) as cli:
                    r = await cli.get(origen)
                    r.raise_for_status()
                    contenido = r.content
                nombre = a.get("nombre_archivo") or origen.split("?")[0].rsplit("/", 1)[-1] or "arte.png"
            else:
                ruta = _ruta_local(origen)
                if not ruta:
                    return error("La ruta no existe o está fuera del proyecto.")
                contenido = ruta.read_bytes()
                nombre = a.get("nombre_archivo") or ruta.name
        except Exception as e:
            return error(f"No pude leer la imagen: {e}")
        if config.MODO_PRUEBA:
            return simulado("imagen", {"nombre": nombre, "bytes": len(contenido)})
        try:
            r = await _post(f"act_{_cuenta(a['cuenta'])}/adimages", {}, archivos={"filename": (nombre, contenido)})
            imagen = next(iter((r.get("images") or {}).values()), {})
            registrar("imagen subida", f"{nombre} · {imagen.get('hash')}")
            return ok({"image_hash": imagen.get("hash"), "nombre": nombre})
        except Exception as e:
            return error(f"ERROR DE META: {e}")

    @tool("meta_crear_creativo",
          "Crea un creativo de imagen única (texto, título, CTA, URL e image_hash). Requiere aprobación humana vigente.",
          esquema({"cuenta": {"type": "string"}, "nombre": {"type": "string"}, "pagina_id": {"type": "string"},
                   "url_destino": {"type": "string"}, "texto": {"type": "string"}, "titulo": {"type": "string"},
                   "descripcion": {"type": "string"}, "cta": {"type": "string", "enum": CTA_VALIDOS},
                   "image_hash": {"type": "string"}, "instagram_user_id": {"type": "string"}},
                  ["cuenta", "nombre", "pagina_id", "url_destino", "texto", "titulo", "cta", "image_hash"]))
    async def meta_crear_creativo(a):
        permitido, motivo = ctx.puede_escribir()
        if not permitido:
            return error(motivo)
        if not _cuenta_permitida(a["cuenta"]):
            return error("BLOQUEADO: cuenta publicitaria no permitida.")
        if config.META_PAGINAS_PERMITIDAS and a["pagina_id"] not in config.META_PAGINAS_PERMITIDAS:
            return error("BLOQUEADO: página no permitida.")
        if not a["url_destino"].startswith("https://"):
            return error("La URL de destino debe empezar con https://")
        link = {"link": a["url_destino"], "message": a["texto"], "name": a["titulo"],
                "image_hash": a["image_hash"],
                "call_to_action": {"type": a["cta"], "value": {"link": a["url_destino"]}}}
        if a.get("descripcion"):
            link["description"] = a["descripcion"]
        datos = {"name": a["nombre"], "object_story_spec": {"page_id": a["pagina_id"], "link_data": link},
                 "instagram_user_id": a.get("instagram_user_id")}
        if config.MODO_PRUEBA:
            return simulado("creativo", datos)
        try:
            r = await _post(f"act_{_cuenta(a['cuenta'])}/adcreatives", datos)
            registrar("creativo creado", f"{r.get('id')} · {a['nombre']}")
            return ok({"id": r.get("id")})
        except Exception as e:
            return error(f"ERROR DE META: {e}")

    @tool("meta_crear_anuncio",
          "Crea un anuncio EN PAUSA en un conjunto con un creativo existente. Úsalo para anuncios NUEVOS; "
          "para cambiar el arte o el texto de un anuncio existente usa meta_asignar_creativo. Requiere aprobación.",
          esquema({"cuenta": {"type": "string"}, "conjunto_id": {"type": "string"}, "nombre": {"type": "string"},
                   "creativo_id": {"type": "string"}}, ["cuenta", "conjunto_id", "nombre", "creativo_id"]))
    async def meta_crear_anuncio(a):
        permitido, motivo = ctx.puede_escribir()
        if not permitido:
            return error(motivo)
        if not _cuenta_permitida(a["cuenta"]):
            return error("BLOQUEADO: cuenta publicitaria no permitida.")
        datos = {"name": a["nombre"], "adset_id": a["conjunto_id"], "status": "PAUSED",
                 "creative": {"creative_id": a["creativo_id"]}}
        if config.MODO_PRUEBA:
            return simulado("anuncio", datos)
        try:
            r = await _post(f"act_{_cuenta(a['cuenta'])}/ads", datos)
            registrar("anuncio creado (pausa)", f"{r.get('id')} · {a['nombre']}")
            return ok({"id": r.get("id"), "estatus": "PAUSED"})
        except Exception as e:
            return error(f"ERROR DE META: {e}")

    @tool("meta_asignar_creativo",
          "Cambia el creativo de un anuncio EXISTENTE (mismo ID de anuncio): así se cambia la imagen o se corrige el "
          "texto sin crear otro anuncio. No toca el estatus. Verifica el resultado. Requiere aprobación humana vigente.",
          esquema({"anuncio_id": {"type": "string"}, "creativo_id": {"type": "string"}},
                  ["anuncio_id", "creativo_id"]))
    async def meta_asignar_creativo(a):
        permitido, motivo = ctx.puede_escribir()
        if not permitido:
            return error(motivo)
        campos = "id,name,status,effective_status,account_id,creative{id,name}"
        try:
            antes = await _get(a["anuncio_id"], {"fields": campos})
            if not _cuenta_permitida(antes.get("account_id", "")):
                return error("BLOQUEADO: el anuncio pertenece a una cuenta no permitida.")
            creativo_antes = (antes.get("creative") or {}).get("id")
            if creativo_antes == a["creativo_id"]:
                return ok({"sin_cambios": True, "nota": "El anuncio ya usa ese creativo."})
            if config.MODO_PRUEBA:
                return simulado("asignar_creativo", {"anuncio": a["anuncio_id"], "creativo_antes": creativo_antes,
                                                     "creativo_despues": a["creativo_id"], "estatus": antes.get("status")})
            r = await _post(a["anuncio_id"], {"creative": {"creative_id": a["creativo_id"]}})
            if not r.get("success", False):
                return error(f"Respuesta inesperada de Meta: {r}")
            despues = await _get(a["anuncio_id"], {"fields": campos})
            if (despues.get("creative") or {}).get("id") != a["creativo_id"]:
                return error("Meta respondió éxito pero el anuncio no muestra el creativo nuevo.")
            if despues.get("status") != antes.get("status"):
                return error(f"ATENCIÓN: el estatus cambió de {antes.get('status')} a {despues.get('status')}.")
            registrar("creativo reemplazado", f"anuncio {a['anuncio_id']}: {creativo_antes} → {a['creativo_id']}")
            return ok({"anuncio": a["anuncio_id"], "creativo_antes": creativo_antes,
                       "creativo_despues": a["creativo_id"], "estatus": despues.get("status"),
                       "nota": "Mismo anuncio, creativo nuevo, estatus sin cambios. Meta lo volverá a revisar."})
        except Exception as e:
            return error(f"ERROR DE META: {e}")

    @tool("meta_cambiar_estatus",
          "Pausa o archiva una campaña, conjunto o anuncio. NO puede activar. Requiere aprobación humana vigente.",
          esquema({"objeto_id": {"type": "string"}, "estatus": {"type": "string", "enum": ["PAUSED", "ARCHIVED"]}},
                  ["objeto_id", "estatus"]))
    async def meta_cambiar_estatus(a):
        permitido, motivo = ctx.puede_escribir()
        if not permitido:
            return error(motivo)
        if a["estatus"] not in ("PAUSED", "ARCHIVED"):
            return error("BLOQUEADO: solo se permite PAUSED o ARCHIVED. La activación es siempre humana.")
        try:
            bloqueo = await verificar_objeto(a["objeto_id"])
            if bloqueo:
                return error(bloqueo)
            if config.MODO_PRUEBA:
                return simulado("estatus", {"objeto": a["objeto_id"], "estatus": a["estatus"]})
            await _post(a["objeto_id"], {"status": a["estatus"]})
            registrar(f"estatus {a['estatus']}", a["objeto_id"])
            return ok({"objeto": a["objeto_id"], "estatus": a["estatus"]})
        except Exception as e:
            return error(f"ERROR DE META: {e}")

    herramientas = [meta_consultar, meta_crear_campana, meta_crear_conjunto, meta_subir_imagen,
                    meta_crear_creativo, meta_crear_anuncio, meta_asignar_creativo, meta_cambiar_estatus]
    return create_sdk_mcp_server(name="meta", version="1.0.0", tools=herramientas), herramientas
