# Agente de Pauta · Slack + Claude en Railway

Servicio para que el equipo cree, suba, edite y analice campañas de Meta **desde Slack**, sin Claude ni Claude Code. Usa los mismos agentes y skills del proyecto `00-mkt-agency` (carpeta `agencia/`) con el Claude Agent SDK, y Monday sigue siendo el registro.

## Cómo se usa (en Slack)

Escríbele al bot por mensaje directo o mencionándolo en un canal. Cada pedido vive en su hilo.

| Quiero… | Ejemplo |
|---|---|
| Crear una campaña con artes | `@agente-pauta Campaña de Tráfico para la agencia sobre agentes de IA en HubSpot, $100 diarios del 27 oct al 9 nov, 2 anuncios, URL https://…` |
| Subirla a Meta | Pasar el elemento a **Listo para montar** en Monday (se monta solo), o `@agente-pauta sube a Meta el elemento "<nombre>"` |
| Editar una campaña | `@agente-pauta en la campaña "<nombre>" cambia la imagen del anuncio <ID> por esta` + adjuntar la imagen en el hilo |
| Ver analítica | `@agente-pauta reporte de la agencia de enero a hoy` |

- Cuando un paso necesita aprobación, el mensaje trae botones **Aprobar** y **Pedir cambios**.
- Se puede seguir la conversación respondiendo en el mismo hilo.
- Al terminar, el bot avisa en el canal y le manda mensaje directo a quien figura como **Solicitante** en Monday (por ejemplo, qué falta si quedó en "Falta info").
- La **oficina** (`/oficina?token=…`) muestra qué agente trabaja, qué espera aprobación, la actividad y el costo en tokens.

## Arquitectura

```
Slack (DM, menciones, botones) ─┐
Monday (webhook de estatus) ────┼─► Servicio (FastAPI + Slack Socket Mode)
                                │        └─► Claude Agent SDK  (cwd = agencia/: CLAUDE.md, agentes, skills)
                                │              ├─ meta_*     → API de Marketing de Meta (usuario de sistema)
                                │              ├─ monday_*   → API de Monday (usuario de servicio)
                                │              └─ slack_notificar → canal + DM al solicitante
                                └─► Bitácora (SQLite en el volumen o Postgres) → Oficina + costo por ejecución
```

## Candados (en código, no solo en instrucciones)

- **No existe forma de activar.** Todo se crea en `PAUSED`; cambiar estatus solo acepta `PAUSED` o `ARCHIVED`.
- **Escrituras solo con aprobación:** las herramientas de Meta y Monday que crean o cambian algo se bloquean hasta que una persona presiona **Aprobar** (o mueve el elemento a "Listo para montar" en Monday).
- **Solo cuentas, páginas y tableros permitidos** (`META_CUENTAS_PERMITIDAS`, `META_PAGINAS_PERMITIDAS`, `MONDAY_TABLEROS_PERMITIDOS`).
- **Monday:** el agente nunca pone etiquetas que disparan tareas automáticas ("Listo para montar", "Prueba", "Producción", "Activa").
- **Secretos fuera del alcance del agente:** los tokens de Meta, Monday y Slack se retiran del entorno al arrancar. El agente no puede usarlos desde la terminal, y `curl`/`wget` están bloqueados.
- **No puede modificar** sus propios agentes, skills ni `CLAUDE.md`.
- **Tope de gasto** por ejecución (`MAX_USD_POR_EJECUCION`) y **modo prueba** (`MODO_PRUEBA=1`): lee Meta de verdad pero no escribe nada.
- **Quién aprueba:** opcionalmente, solo los IDs de `SLACK_APROBADORES`.

## Lo que necesitas antes de desplegar

1. **API key de Anthropic** (console.anthropic.com). Es pago por uso, aparte de los asientos de Claude.
2. **App de Slack** creada con `slack_manifest.yml`.
3. **Token de Meta de usuario de sistema** con `ads_management` y `ads_read`, con la cuenta publicitaria y la página asignadas.
4. **Token de API de Monday** de un usuario de servicio con acceso al tablero.
5. **Cuenta de Railway** y el repositorio en GitHub (privado).

## Paso a paso

### 1. Repositorio
Sube esta carpeta a un repositorio **privado** de GitHub. `agencia/` es una copia del proyecto `00-mkt-agency`. Cuando cambies agentes o skills, actualiza esa carpeta y haz push: Railway vuelve a desplegar solo.

### 2. Slack
1. En **api.slack.com/apps** → **Create New App** → **From a manifest** → elige el workspace → pega `slack_manifest.yml`.
2. **Install to Workspace**. Copia el **Bot User OAuth Token** (`xoxb-…`) → `SLACK_BOT_TOKEN`.
3. En **Basic Information → App-Level Tokens** → **Generate** con el scope `connections:write`. Copia el token (`xapp-…`) → `SLACK_APP_TOKEN`.
4. Crea el canal de avisos (ej. `#agentesequipomajo`), invita al bot (`/invite @agente-pauta`) y copia el ID del canal (clic en el nombre → abajo del todo) → `SLACK_CANAL_AVISOS`.
5. Si tu workspace pide aprobación de apps, un admin tiene que aprobarla.

### 3. Meta (usuario de sistema)
1. **Business settings → Users → System users → Add**: nombre `agente-pauta`, rol Employee.
2. **Assign assets**: la cuenta publicitaria (Manage campaigns) y la página (Create ads).
3. **Generate new token** con la app `ads_management_test` y los permisos `ads_management` y `ads_read` → `META_ACCESS_TOKEN`.

### 4. Monday
Con un usuario de servicio que tenga acceso al tablero: **avatar → Developers → My access tokens → Copy** → `MONDAY_API_TOKEN`.

### 5. Railway
1. **New Project → Deploy from GitHub repo** → elige el repositorio. Detecta el `Dockerfile` y `railway.json`.
2. **Add Volume** al servicio, montado en **`/data`**. Ahí viven la bitácora, las sesiones del agente y los entregables.
3. **Variables:** copia las de `.env.example` y llénalas. Deja `MODO_PRUEBA=1`. Genera `OFICINA_TOKEN` y `MONDAY_WEBHOOK_SECRET` largos y aleatorios.
4. **Settings → Networking → Generate Domain.** Copia el dominio a `PUBLIC_URL` y vuelve a desplegar.
5. Revisa `https://<dominio>/health`: debe responder `{"ok": true, "modo_prueba": true, "slack": true}`.

Mantén **1 réplica**: Socket Mode y la bitácora en SQLite asumen una sola instancia. Para más de una, usa Postgres (`DATABASE_URL`) y revisa Socket Mode.

### 6. Probar en modo prueba
1. Mándale un DM al bot: `hola`. Debe responder con lo que puede hacer.
2. Corre los 4 flujos de la tabla de arriba. En modo prueba, todo lo de Meta sale como "MODO_PRUEBA: no se envió nada a Meta" con lo que se habría enviado; Monday y Slack sí funcionan.
3. Abre la oficina: `https://<dominio>/oficina?token=<OFICINA_TOKEN>`.

### 7. Monday dispara el montaje
En el tablero: **Integrate → Webhooks → "When a column changes, send a webhook"** (columna *Estatus agente*), con la URL
`https://<dominio>/webhooks/monday/<MONDAY_WEBHOOK_SECRET>`.
El servicio solo actúa cuando el estatus cambia a **Listo para montar**.
**Desactiva la tarea programada que hoy monta cada hora**, o los dos procesarán el mismo elemento.

### 8. Producción
Cuando los flujos salgan bien en modo prueba: `MODO_PRUEBA=0` y redeploy. Desde ese momento las escrituras en Meta son reales, siempre en pausa.

## Costos y consumo
- **Railway:** el plan con volumen y un servicio siempre encendido.
- **Anthropic:** pago por tokens. Cada ejecución guarda tokens de entrada, salida y caché, y el costo estimado. La oficina muestra el total del día y del mes.
- **Para gastar menos:** `AGENT_MODEL=sonnet` (por defecto); el tope por ejecución está en `MAX_USD_POR_EJECUCION`.

## Desarrollo local
```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt pytest
cp .env.example .env   # llénalo
set -a && source .env && set +a
uvicorn app.main:app --reload
python -m pytest -q tests
```

## Estado y pendientes
- **Probado:** candados, formato de Slack, webhook de Monday (verificación y filtro), oficina, archivos y arranque del agente con sus herramientas, agentes y skills (pruebas en `tests/`).
- **Sin probar contra cuentas reales desde el servidor:** las llamadas de escritura a la API de Meta y la subida de archivos a Monday. Por eso arranca en `MODO_PRUEBA=1`.
- **No se construyó aquí la imagen Docker.** El primer despliegue en Railway la construye; si falla, revisa el log del build.
- **La oficina** es una versión funcional con los datos reales. El diseño de personajes de Amaya puede montarse encima: usa el JSON de `/api/estado`.
