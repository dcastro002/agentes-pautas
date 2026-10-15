"""Herramientas de Monday (API GraphQL) con candados.

- Solo tableros de MONDAY_TABLEROS_PERMITIDOS (si se definen).
- Las escrituras exigen aprobación humana vigente (ctx.aprobado).
- Nunca se ponen etiquetas que disparan tareas automáticas (MONDAY_ETIQUETAS_PROHIBIDAS / _INDICES_).
"""
import json
import mimetypes
import re
from pathlib import Path

import httpx
from claude_agent_sdk import create_sdk_mcp_server, tool

from .. import config, db
from ..contexto import Contexto
from .comun import cargar_json, error, esquema, ok

API = "https://api.monday.com/v2"
API_ARCHIVOS = "https://api.monday.com/v2/file"


async def gql(consulta: str, variables: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=90) as cli:
        r = await cli.post(API, json={"query": consulta, "variables": variables or {}},
                           headers={"Authorization": config.MONDAY_API_TOKEN})
    cuerpo = r.json()
    if r.status_code >= 400 or cuerpo.get("errors") or cuerpo.get("error_message"):
        raise RuntimeError(json.dumps(cuerpo.get("errors") or cuerpo.get("error_message") or cuerpo, ensure_ascii=False)[:1500])
    return cuerpo.get("data", {})


def tablero_permitido(board_id) -> bool:
    return not config.MONDAY_TABLEROS_PERMITIDOS or str(board_id) in config.MONDAY_TABLEROS_PERMITIDOS


def valores_prohibidos(valores: dict) -> str | None:
    """Revisa que no se ponga una etiqueta que dispare tareas automáticas."""
    prohibidas = {e.lower() for e in config.MONDAY_ETIQUETAS_PROHIBIDAS}
    indices = set(config.MONDAY_INDICES_PROHIBIDOS)
    for col, val in valores.items():
        etiqueta, indice = None, None
        if isinstance(val, dict):
            etiqueta, indice = val.get("label"), val.get("index")
        elif isinstance(val, str):
            etiqueta = val
        if etiqueta and str(etiqueta).strip().lower() in prohibidas:
            return f"BLOQUEADO: no puedo poner la etiqueta '{etiqueta}' (dispara tareas automáticas o la pone una persona)."
        if indice is not None and f"{col}:{indice}" in indices:
            return f"BLOQUEADO: no puedo poner el índice {indice} en {col} (lo pone una persona)."
    return None


def normalizar_valores(valores: dict) -> dict:
    """Corrige formatos que Monday rechaza o ignora en silencio (link como texto plano, notas largas)."""
    salida = {}
    for col, val in valores.items():
        if col.startswith("link_"):
            if isinstance(val, str) and val.strip():
                val = {"url": val.strip(), "text": "Ver campaña en Ads Manager"}
            elif isinstance(val, dict) and val.get("url") and not val.get("text"):
                val = {**val, "text": "Ver campaña en Ads Manager"}
        elif col.startswith("long_text_") and isinstance(val, str):
            val = {"text": val}
        salida[col] = val
    return salida


async def board_de_item(item_id: str) -> str | None:
    d = await gql("query ($i:[ID!]) { items(ids:$i) { board { id } } }", {"i": [str(item_id)]})
    items = d.get("items") or []
    return str(items[0]["board"]["id"]) if items else None


async def correos_solicitantes(item_id: str, columna: str) -> list[str]:
    d = await gql("query ($i:[ID!], $c:[String!]) { items(ids:$i) { column_values(ids:$c) { value } } }",
                  {"i": [str(item_id)], "c": [columna]})
    items = d.get("items") or []
    if not items or not items[0]["column_values"]:
        return []
    valor = items[0]["column_values"][0].get("value")
    personas = (json.loads(valor) if valor else {}).get("personsAndTeams", [])
    ids = [str(p["id"]) for p in personas if p.get("kind") == "person"]
    if not ids:
        return []
    u = await gql("query ($u:[ID!]) { users(ids:$u) { email } }", {"u": ids})
    return [x["email"] for x in u.get("users", []) if x.get("email")]


def crear_servidor(ctx: Contexto):
    def registrar(accion: str, detalle: str):
        ctx.escrituras.append(f"{accion}: {detalle}")
        db.evento(ctx.conv_id, "gestor-solicitudes", accion, detalle)

    @tool("monday_leer_elementos",
          "Lee elementos de Monday por ID: nombre, tablero, todas sus columnas (id, texto, valor) y sus archivos "
          "adjuntos (asset_id, nombre, public_url temporal).",
          esquema({"ids_json": {"type": "string", "description": "JSON, ej. [\"13272976029\"]"}}, ["ids_json"]))
    async def monday_leer_elementos(a):
        ids = [str(x) for x in cargar_json(a["ids_json"], [])]
        try:
            d = await gql("""query ($i:[ID!]) { items(ids:$i) { id name created_at url board { id name }
                 column_values { id type text value }
                 assets { id name file_extension public_url } } }""", {"i": ids})
            items = [it for it in d.get("items", []) if tablero_permitido(it["board"]["id"])]
            return ok(items)
        except Exception as e:
            return error(f"ERROR DE MONDAY: {e}")

    @tool("monday_buscar",
          "Busca elementos en un tablero por texto en el nombre y/o por etiqueta de estatus. Devuelve id, nombre y estatus.",
          esquema({"tablero_id": {"type": "string"}, "texto": {"type": "string"},
                   "estatus": {"type": "string"}, "columna_estatus": {"type": "string"}}, ["tablero_id"]))
    async def monday_buscar(a):
        if not tablero_permitido(a["tablero_id"]):
            return error("BLOQUEADO: tablero no permitido.")
        col = a.get("columna_estatus") or config.MONDAY_COLUMNA_ESTATUS
        texto = (a.get("texto") or "").lower()
        estatus = (a.get("estatus") or "").lower()
        resultados, cursor = [], None
        try:
            primera = await gql("""query ($b:[ID!], $c:[String!]) { boards(ids:$b) { items_page(limit:200) {
                 cursor items { id name column_values(ids:$c) { text } } } } }""", {"b": [a["tablero_id"]], "c": [col]})
            pagina = primera["boards"][0]["items_page"]
            while True:
                for it in pagina["items"]:
                    est = (it["column_values"][0]["text"] if it["column_values"] else "") or ""
                    if texto and texto not in it["name"].lower():
                        continue
                    if estatus and estatus != est.lower():
                        continue
                    resultados.append({"id": it["id"], "nombre": it["name"], "estatus": est})
                cursor = pagina.get("cursor")
                if not cursor or len(resultados) > 300:
                    break
                sig = await gql("""query ($k:String!, $c:[String!]) { next_items_page(limit:200, cursor:$k) {
                     cursor items { id name column_values(ids:$c) { text } } } }""", {"k": cursor, "c": [col]})
                pagina = sig["next_items_page"]
            return ok({"resultados": resultados, "total": len(resultados)})
        except Exception as e:
            return error(f"ERROR DE MONDAY: {e}")

    @tool("monday_descargar_archivo",
          "Descarga un archivo adjunto de Monday (por asset_id) a una carpeta dentro de _Entregables, para leerlo "
          "(ej. un brief en Excel con python3 y openpyxl). Devuelve la ruta local.",
          esquema({"asset_id": {"type": "string"},
                   "carpeta": {"type": "string", "description": "Relativa a _Entregables, ej. agencia/2026-10/descargas"}},
                  ["asset_id", "carpeta"]))
    async def monday_descargar_archivo(a):
        carpeta = (config.ENTREGABLES_DIR / a["carpeta"]).resolve()
        if config.ENTREGABLES_DIR.resolve() not in [carpeta, *carpeta.parents]:
            return error("La carpeta debe estar dentro de _Entregables.")
        try:
            d = await gql("query ($a:[ID!]!) { assets(ids:$a) { id name public_url } }", {"a": [a["asset_id"]]})
            asset = (d.get("assets") or [None])[0]
            if not asset:
                return error("No encontré ese archivo.")
            async with httpx.AsyncClient(timeout=120, follow_redirects=True) as cli:
                r = await cli.get(asset["public_url"])
                r.raise_for_status()
            carpeta.mkdir(parents=True, exist_ok=True)
            nombre = re.sub(r"[^\w.\-]+", "_", asset["name"])
            destino = carpeta / nombre
            destino.write_bytes(r.content)
            return ok({"ruta": str(destino.relative_to(config.AGENCIA_DIR.resolve()) if destino.is_relative_to(config.AGENCIA_DIR.resolve()) else destino),
                       "ruta_absoluta": str(destino), "bytes": len(r.content), "public_url": asset["public_url"]})
        except Exception as e:
            return error(f"ERROR DE MONDAY: {e}")

    @tool("monday_crear_elemento",
          "Crea un elemento en un tablero con valores de columnas (JSON). Requiere aprobación humana vigente.",
          esquema({"tablero_id": {"type": "string"}, "nombre": {"type": "string"},
                   "valores_json": {"type": "string", "description": "JSON {id_columna: valor}"}},
                  ["tablero_id", "nombre"]))
    async def monday_crear_elemento(a):
        permitido, motivo = ctx.puede_escribir()
        if not permitido:
            return error(motivo)
        if not tablero_permitido(a["tablero_id"]):
            return error("BLOQUEADO: tablero no permitido.")
        valores = cargar_json(a.get("valores_json"), {})
        bloqueo = valores_prohibidos(valores)
        if bloqueo:
            return error(bloqueo)
        try:
            d = await gql("mutation ($b:ID!, $n:String!, $v:JSON) { create_item(board_id:$b, item_name:$n, column_values:$v) { id url } }",
                          {"b": a["tablero_id"], "n": a["nombre"], "v": json.dumps(valores)})
            item = d["create_item"]
            ctx.item_monday = ctx.item_monday or str(item["id"])
            registrar("elemento creado", f"{item['id']} · {a['nombre']}")
            return ok(item)
        except Exception as e:
            return error(f"ERROR DE MONDAY: {e}")

    @tool("monday_actualizar",
          "Cambia columnas de un elemento (estatus, notas, link…). Formatos: estatus {\"label\": \"...\"}, "
          "notas (long_text_*) {\"text\": \"...\"}, link (link_*) {\"url\": \"https://...\", \"text\": \"...\"}. "
          "No puede poner etiquetas que disparan tareas automáticas. Requiere aprobación humana vigente.",
          esquema({"tablero_id": {"type": "string"}, "item_id": {"type": "string"},
                   "valores_json": {"type": "string"}}, ["tablero_id", "item_id", "valores_json"]))
    async def monday_actualizar(a):
        permitido, motivo = ctx.puede_escribir()
        if not permitido:
            return error(motivo)
        if not tablero_permitido(a["tablero_id"]):
            return error("BLOQUEADO: tablero no permitido.")
        valores = normalizar_valores(cargar_json(a["valores_json"], {}))
        bloqueo = valores_prohibidos(valores)
        if bloqueo:
            return error(bloqueo)
        try:
            d = await gql("mutation ($b:ID!, $i:ID!, $v:JSON!) { change_multiple_column_values(board_id:$b, item_id:$i, column_values:$v) { id } }",
                          {"b": a["tablero_id"], "i": a["item_id"], "v": json.dumps(valores)})
            registrar("elemento actualizado", f"{a['item_id']} · {', '.join(valores.keys())}")
            return ok(d["change_multiple_column_values"])
        except Exception as e:
            return error(f"ERROR DE MONDAY: {e}")

    @tool("monday_subir_archivo",
          "Adjunta un archivo del proyecto (ruta relativa al proyecto, ej. _Entregables/...xlsx o .png) a una columna "
          "de archivos de un elemento. Requiere aprobación humana vigente.",
          esquema({"item_id": {"type": "string"}, "columna": {"type": "string"}, "ruta": {"type": "string"}},
                  ["item_id", "columna", "ruta"]))
    async def monday_subir_archivo(a):
        permitido, motivo = ctx.puede_escribir()
        if not permitido:
            return error(motivo)
        ruta = (config.AGENCIA_DIR / a["ruta"]).resolve()
        raices = [config.AGENCIA_DIR.resolve(), config.ENTREGABLES_DIR.resolve()]
        if not ruta.is_file() or not any(r in ruta.parents for r in raices):
            return error("El archivo no existe o está fuera del proyecto.")
        if not re.fullmatch(r"[a-z0-9_]+", a["columna"]):
            return error("Columna no válida.")
        try:
            board = await board_de_item(a["item_id"])
            if not board or not tablero_permitido(board):
                return error("BLOQUEADO: elemento no encontrado o de un tablero no permitido.")
            consulta = ('mutation ($file: File!) { add_file_to_column (item_id: %s, column_id: "%s", file: $file) { id } }'
                        % (int(a["item_id"]), a["columna"]))
            tipo = mimetypes.guess_type(ruta.name)[0] or "application/octet-stream"
            async with httpx.AsyncClient(timeout=180) as cli:
                r = await cli.post(API_ARCHIVOS, data={"query": consulta},
                                   files={"variables[file]": (ruta.name, ruta.read_bytes(), tipo)},
                                   headers={"Authorization": config.MONDAY_API_TOKEN})
            cuerpo = r.json()
            if r.status_code >= 400 or cuerpo.get("errors") or cuerpo.get("error_message"):
                return error(f"ERROR DE MONDAY: {json.dumps(cuerpo, ensure_ascii=False)[:1500]}")
            registrar("archivo adjuntado", f"{a['item_id']} · {a['columna']} · {ruta.name}")
            return ok({"asset_id": cuerpo["data"]["add_file_to_column"]["id"], "archivo": ruta.name})
        except Exception as e:
            return error(f"ERROR DE MONDAY: {e}")

    herramientas = [monday_leer_elementos, monday_buscar, monday_descargar_archivo, monday_crear_elemento,
                    monday_actualizar, monday_subir_archivo]
    return create_sdk_mcp_server(name="monday", version="1.0.0", tools=herramientas), herramientas
