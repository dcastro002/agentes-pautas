"""Configuración del servicio. Todo sale de variables de entorno.

Los secretos se leen aquí y se BORRAN de os.environ al arrancar, para que el
proceso del agente (Claude Code) no los herede: el agente solo puede tocar Meta,
Monday y Slack a través de las herramientas del servicio, que tienen candados.
"""
import logging
import os
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _limpio(valor: str) -> str:
    """Quita espacios y comillas que a veces se cuelan al pegar valores en Railway."""
    valor = (valor or "").strip()
    while len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
        valor = valor[1:-1].strip()
    return valor


def _env(nombre: str, defecto: str = "") -> str:
    return _limpio(os.environ.get(nombre, defecto)) or defecto


def _secreto(nombre: str) -> str:
    return _limpio(os.environ.pop(nombre, ""))


def _lista(nombre: str, defecto: str = "") -> list[str]:
    return [x.strip() for x in _env(nombre, defecto).split(",") if x.strip()]


# --- Secretos (se retiran del entorno) -------------------------------------
SLACK_BOT_TOKEN = _secreto("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = _secreto("SLACK_APP_TOKEN")
META_ACCESS_TOKEN = _secreto("META_ACCESS_TOKEN")
MONDAY_API_TOKEN = _secreto("MONDAY_API_TOKEN")
MONDAY_WEBHOOK_SECRET = _secreto("MONDAY_WEBHOOK_SECRET")
OFICINA_TOKEN = _secreto("OFICINA_TOKEN")
DATABASE_URL = _secreto("DATABASE_URL")
GOOGLE_ADS_CLIENT_ID = _secreto("GOOGLE_ADS_CLIENT_ID")
GOOGLE_ADS_CLIENT_SECRET = _secreto("GOOGLE_ADS_CLIENT_SECRET")
GOOGLE_ADS_REFRESH_TOKEN = _secreto("GOOGLE_ADS_REFRESH_TOKEN")
# Opcional: desde sep-2026 el acceso vive en el proyecto de Google Cloud y el developer token ya no hace falta.
GOOGLE_ADS_DEVELOPER_TOKEN = _secreto("GOOGLE_ADS_DEVELOPER_TOKEN")
# LinkedIn: token de acceso (dura 60 días) o, si LinkedIn los da, refresh token + cliente para renovarlo solo
LINKEDIN_ACCESS_TOKEN = _secreto("LINKEDIN_ACCESS_TOKEN")
LINKEDIN_REFRESH_TOKEN = _secreto("LINKEDIN_REFRESH_TOKEN")
LINKEDIN_CLIENT_ID = _secreto("LINKEDIN_CLIENT_ID")
LINKEDIN_CLIENT_SECRET = _secreto("LINKEDIN_CLIENT_SECRET")
# ANTHROPIC_API_KEY se queda en el entorno: el agente la necesita.

# --- Rutas -----------------------------------------------------------------
DATA_DIR = Path(_env("DATA_DIR", str(RAIZ / "datos")))
AGENCIA_DIR = Path(_env("AGENCIA_DIR", str(RAIZ / "agencia")))
ENTREGABLES_DIR = AGENCIA_DIR / "_Entregables"
if not DATABASE_URL:
    DATABASE_URL = f"sqlite:///{DATA_DIR / 'bitacora.db'}"

# --- Agente ----------------------------------------------------------------
AGENT_MODEL = _env("AGENT_MODEL", "sonnet")
MAX_USD_POR_EJECUCION = float(_env("MAX_USD_POR_EJECUCION", "5"))
MAX_TURNOS = int(_env("MAX_TURNOS", "250"))
MAX_CONCURRENCIA = int(_env("MAX_CONCURRENCIA", "2"))
# Modo prueba: lee Meta de verdad, pero NO crea ni modifica nada en Meta.
MODO_PRUEBA = _env("MODO_PRUEBA", "1") not in ("0", "false", "no")
CHROME = _env("CHROME", "/usr/bin/chromium")

# --- Slack -----------------------------------------------------------------
SLACK_CANAL_AVISOS = _env("SLACK_CANAL_AVISOS")          # ID del canal, ej. C0123ABC
SLACK_RESPONSABLE_EMAIL = _env("SLACK_RESPONSABLE_EMAIL")  # quien aprueba (se menciona en avisos)
SLACK_APROBADORES = _lista("SLACK_APROBADORES")  # IDs de Slack que pueden aprobar; vacío = cualquiera en el hilo

# --- Meta ------------------------------------------------------------------
META_API_VERSION_DEFECTO = "v26.0"
_version = _env("META_API_VERSION", META_API_VERSION_DEFECTO)
if re.fullmatch(r"v?\d+\.\d+", _version):
    META_API_VERSION = _version if _version.startswith("v") else f"v{_version}"
else:
    # No se registra el valor: si alguien pegó ahí un token, no debe quedar en los logs.
    logging.getLogger("agentes").warning(
        "META_API_VERSION no tiene el formato vNN.N (%d caracteres); uso %s.", len(_version), META_API_VERSION_DEFECTO)
    META_API_VERSION = META_API_VERSION_DEFECTO
META_CUENTAS_PERMITIDAS = [c.replace("act_", "") for c in _lista("META_CUENTAS_PERMITIDAS")]
META_PAGINAS_PERMITIDAS = _lista("META_PAGINAS_PERMITIDAS")

# --- Google Ads ------------------------------------------------------------
GOOGLE_ADS_API_VERSION = (_env("GOOGLE_ADS_API_VERSION", "v26").lower().lstrip("v").split(".")[0]) or "26"
GOOGLE_ADS_API_VERSION = f"v{GOOGLE_ADS_API_VERSION}" if GOOGLE_ADS_API_VERSION.isdigit() else "v26"
# MCC (cuenta de administrador) por la que se entra, sin guiones
GOOGLE_ADS_LOGIN_CUSTOMER_ID = _env("GOOGLE_ADS_LOGIN_CUSTOMER_ID").replace("-", "")
GOOGLE_ADS_CUENTAS_PERMITIDAS = [c.replace("-", "") for c in _lista("GOOGLE_ADS_CUENTAS_PERMITIDAS")]
# Tope de seguridad por campaña (MXN diarios). 0 = sin tope.
GOOGLE_ADS_PRESUPUESTO_MAX_DIARIO = float(_env("GOOGLE_ADS_PRESUPUESTO_MAX_DIARIO", "500"))
GOOGLE_ADS_MONEDA = _env("GOOGLE_ADS_MONEDA", "MXN")

# --- LinkedIn Ads ----------------------------------------------------------
_li_version = _env("LINKEDIN_API_VERSION", "202610").replace("-", "")
LINKEDIN_API_VERSION = _li_version if re.fullmatch(r"20\d{4}", _li_version) else "202610"
LINKEDIN_CUENTAS_PERMITIDAS = [re.sub(r"\D", "", c) for c in _lista("LINKEDIN_CUENTAS_PERMITIDAS")]
# Tope de seguridad por campaña (diario, en la moneda de la cuenta). 0 = sin tope.
LINKEDIN_PRESUPUESTO_MAX_DIARIO = float(_env("LINKEDIN_PRESUPUESTO_MAX_DIARIO", "500"))
LINKEDIN_MONEDA = _env("LINKEDIN_MONEDA", "MXN")

# Hosts de los que el servidor puede descargar imágenes (public_url de Monday)
HOSTS_IMAGENES = _lista("HOSTS_IMAGENES", "monday.com,files-monday-com.s3.amazonaws.com")

# --- Monday ----------------------------------------------------------------
MONDAY_TABLEROS_PERMITIDOS = _lista("MONDAY_TABLEROS_PERMITIDOS")
MONDAY_COLUMNA_ESTATUS = _env("MONDAY_COLUMNA_ESTATUS", "color_mm7vt5cg")
MONDAY_ESTATUS_DISPARO = _env("MONDAY_ESTATUS_DISPARO", "Listo para montar")
MONDAY_COLUMNA_SOLICITANTE = _env("MONDAY_COLUMNA_SOLICITANTE", "multiple_person_mm7vwycn")
MONDAY_COLUMNA_NOTAS = _env("MONDAY_COLUMNA_NOTAS", "long_text_mm7vmg76")
# Estatus que avisan por DM a quien creó el elemento y a su Solicitante
MONDAY_ESTATUS_AVISO = _lista("MONDAY_ESTATUS_AVISO", "Error,Falta info")
# 1 = avisar a la responsable cuando alguien crea un elemento a mano en el tablero
AVISAR_ELEMENTO_NUEVO = _env("AVISAR_ELEMENTO_NUEVO", "1") != "0"
# Etiquetas que el agente nunca puede poner (disparan tareas automáticas)
MONDAY_ETIQUETAS_PROHIBIDAS = _lista("MONDAY_ETIQUETAS_PROHIBIDAS", "Listo para montar,Prueba,Producción,Activa")
# Mismos candados por índice de estatus: "columna:índice"
MONDAY_INDICES_PROHIBIDOS = _lista("MONDAY_INDICES_PROHIBIDOS",
                                   "color_mm7vt5cg:7,color_mm7vt5cg:1,color_mm7vqz13:152,color_mm7vqz13:107")

# --- Web -------------------------------------------------------------------
PUBLIC_URL = _env("PUBLIC_URL").rstrip("/")


def preparar_directorios() -> None:
    """Crea las carpetas persistentes y enlaza _Entregables al volumen de datos."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "claude").mkdir(parents=True, exist_ok=True)
    persistente = DATA_DIR / "entregables"
    persistente.mkdir(parents=True, exist_ok=True)
    if ENTREGABLES_DIR.is_symlink():
        return
    if ENTREGABLES_DIR.exists():
        # Copia lo que traiga la imagen (README) al volumen y deja un enlace.
        # El volumen es otro disco: rename() falla entre discos, por eso se copia.
        import shutil
        for p in ENTREGABLES_DIR.iterdir():
            destino = persistente / p.name
            if destino.exists():
                continue
            if p.is_dir():
                shutil.copytree(p, destino)
            else:
                shutil.copy2(p, destino)
        shutil.rmtree(ENTREGABLES_DIR)
    ENTREGABLES_DIR.symlink_to(persistente, target_is_directory=True)
