import json
import math
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

MAX_BYTES_IMAGEN = 10 * 1024 * 1024
FIRMAS_IMAGEN = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF87a", b"GIF89a")


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


def numero_positivo(valor) -> float | None:
    """Convierte a número finito y mayor a 0; si no se puede, None (rechaza NaN, infinito, texto y negativos)."""
    try:
        x = float(valor)
    except (TypeError, ValueError):
        return None
    return round(x, 2) if math.isfinite(x) and x > 0 else None


def host_permitido(url: str, hosts: list[str]) -> bool:
    p = urlparse(url)
    h = (p.hostname or "").lower()
    return p.scheme == "https" and any(h == x or h.endswith("." + x) for x in hosts)


async def descargar_imagen(url: str, hosts: list[str]) -> bytes:
    """Descarga una imagen solo de hosts permitidos (también en cada redirección), con tope de tamaño
    y verificando que de verdad sea PNG, JPG o GIF."""
    actual = url
    async with httpx.AsyncClient(timeout=60, follow_redirects=False) as cli:
        for _ in range(4):
            if not host_permitido(actual, hosts):
                raise ValueError(f"Host no permitido para descargar imágenes: {urlparse(actual).hostname}")
            r = await cli.get(actual)
            if r.is_redirect:
                actual = urljoin(actual, r.headers.get("location", ""))
                continue
            r.raise_for_status()
            contenido = r.content
            break
        else:
            raise ValueError("Demasiadas redirecciones al descargar la imagen")
    if len(contenido) > MAX_BYTES_IMAGEN:
        raise ValueError("La imagen pesa más de 10 MB")
    if not contenido.startswith(FIRMAS_IMAGEN):
        raise ValueError("El archivo descargado no es PNG, JPG ni GIF")
    return contenido
