"""Configuración del servicio. Todo sale de variables de entorno.

Los secretos se leen aquí y se BORRAN de os.environ al arrancar, para que el
proceso del agente (Claude Code) no los herede: el agente solo puede tocar Meta,
Monday y Slack a través de las herramientas del servicio, que tienen candados.
"""
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _env(nombre: str, defecto: str = "") -> str:
    return os.environ.get(nombre, defecto).strip()


def _secreto(nombre: str) -> str:
    valor = os.environ.pop(nombre, "").strip()
    return valor


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
META_API_VERSION = _env("META_API_VERSION", "v26.0")
META_CUENTAS_PERMITIDAS = [c.replace("act_", "") for c in _lista("META_CUENTAS_PERMITIDAS")]
META_PAGINAS_PERMITIDAS = _lista("META_PAGINAS_PERMITIDAS")

# --- Monday ----------------------------------------------------------------
MONDAY_TABLEROS_PERMITIDOS = _lista("MONDAY_TABLEROS_PERMITIDOS")
MONDAY_COLUMNA_ESTATUS = _env("MONDAY_COLUMNA_ESTATUS", "color_mm7vt5cg")
MONDAY_ESTATUS_DISPARO = _env("MONDAY_ESTATUS_DISPARO", "Listo para montar")
MONDAY_COLUMNA_SOLICITANTE = _env("MONDAY_COLUMNA_SOLICITANTE", "multiple_person_mm7vwycn")
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
        # Mueve lo que traiga la imagen (README) al volumen y deja un enlace
        for p in ENTREGABLES_DIR.iterdir():
            destino = persistente / p.name
            if not destino.exists():
                p.rename(destino)
        try:
            ENTREGABLES_DIR.rmdir()
        except OSError:
            return
    ENTREGABLES_DIR.symlink_to(persistente, target_is_directory=True)
