import json
from typing import Any


def ok(datos: Any) -> dict:
    texto = datos if isinstance(datos, str) else json.dumps(datos, ensure_ascii=False, indent=1, default=str)
    return {"content": [{"type": "text", "text": texto}]}


def error(mensaje: str) -> dict:
    return {"content": [{"type": "text", "text": mensaje}], "is_error": True}


def esquema(propiedades: dict, requeridas: list[str]) -> dict:
    return {"type": "object", "properties": propiedades, "required": requeridas}


def cargar_json(texto: str | None, defecto: Any) -> Any:
    if texto is None or str(texto).strip() == "":
        return defecto
    if isinstance(texto, (dict, list)):
        return texto
    return json.loads(texto)
