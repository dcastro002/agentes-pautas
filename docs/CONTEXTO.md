# Contexto · Agentes de pauta

Fuente de verdad del proyecto para quien entra al repo (persona o Claude). Actualizado: 17 nov 2026.
Responsable técnico: David Castro. Aprobadora: Amaya Gutiérrez. Directora de pautas: María José Gastelum (Majo).

Las reglas de código están en [`CLAUDE.md`](../CLAUDE.md). Este doc explica qué es, cómo está armado y en qué va.

---

## 1. Qué es

Servicio `agentes-pauta` desplegado en **Railway**: un bot de Slack + webhooks de Monday que ejecutan agentes del **Claude Agent SDK (Python)** para crear campañas publicitarias. Todo se crea **en pausa o borrador** y requiere **aprobación humana con botón en Slack**.

- Repo en GitHub: `agentes-pauta` (rama `main` protegida; cambios por rama + PR; Railway despliega desde `main` después de CI).
- El agente trabaja sobre la carpeta `agencia/` (copia del proyecto `00-mkt-agency`): `CLAUDE.md`, agentes, skills, `_Context/` (Estrategia.md, Cuentas.md), `_BrandKIT/`, `_Entregables/` (en volumen de Railway, `/data/entregables`).
- Objetivo general del programa: agencia autónoma con IA; medir eficiencia operativa (tiempo) y de costos.

## 2. Arquitectura

- **Agent SDK** `ClaudeAgentOptions`:
  - `cwd=agencia`
  - `add_dirs=[ENTREGABLES_DIR]`: symlink al volumen. Sin esto, el agente no podía escribir.
  - `setting_sources=["project"]`, `permission_mode="dontAsk"`, `max_budget_usd`
  - skills: `campana-meta`, `campana-google`, `campana-linkedin`, `editar-campana`, `analizar-campanas`, `pieza-contenido`
- **Hooks PreToolUse**:
  - `guardia_bash`: bloquea red (incluye googleads, oauth2, api.linkedin).
  - `guardia_archivos`.
- **MCP in-process**: `meta`, `monday`, `slack`, `google_ads`, `linkedin`.
- **Aprobación**: solo con botón de Slack (`ctx.puede_escribir()`). Si el usuario contesta "sí" con texto, no cuenta. El marcador `[[APROBACION]]` muestra los botones.
- **`MODO_PRUEBA`** (global):
  - Google usa `validateOnly`.
  - LinkedIn y Meta simulan las escrituras.
  - Con `MODO_PRUEBA=0` se crea de verdad (Meta/Google en pausa, LinkedIn en DRAFT).
- **Webhooks de Monday** (`app/main.py`), deduplicados por `triggerUuid`:
  - `create_pulse` → `avisos.avisar_nuevo`: avisa a Majo si alguien crea el elemento a mano.
  - Estatus Error / Falta info → `avisos.avisar_problema`: avisa por DM al solicitante y al creador.
  - "Listo para montar" → lanza el agente.
- **Health**: `/health`, `/health/meta`, `/health/google-ads`, `/health/linkedin`.

### Archivos clave

- **`app/config.py`**
  - `_limpio` y `_secreto`: los secretos se sacan del entorno.
  - Normaliza `META_API_VERSION`.
  - `preparar_directorios` usa copy + rmtree, no rename (rename fallaba con cross-device link).
- **`app/runner.py`**: opciones del agente, `allowed_tools`, log de `permiso_negado`.
- **`app/avisos.py`**: avisos de Slack por eventos de Monday.
- **`app/tools/comun.py`**
  - `numero_positivo`: rechaza NaN, inf y negativos.
  - `descargar_imagen`: solo hosts permitidos en cada redirect, tope de 10 MB, valida magic bytes PNG/JPG/GIF.
- **`app/tools/meta.py`**: `advantage_audience=0` por defecto; los creativos se crean antes que la campaña.
- **`app/tools/monday.py`**
  - Columnas link → `{url,text}`; long_text → `{text}`.
  - `monday_actualizar(agregar_notas=true)`: agrega al final de las notas, no las reemplaza.
- **`app/tools/google_ads.py`** (REST v26)
  - `google_ads_consultar`: GAQL solo SELECT, solo cuentas permitidas.
  - `google_ads_montar_busqueda`: un `googleAds:mutate` atómico con IDs temporales; campaña PAUSED.
  - `google_ads_agregar_anuncio`, `google_ads_agregar_palabras`, `google_ads_pausar`.
- **`app/tools/linkedin.py`** (`LinkedIn-Version: 202610`)
  - `linkedin_consultar`: solo rutas de la cuenta, no catálogos de targeting.
  - `linkedin_montar_campana`: imágenes → posts ocultos (dark posts) → grupo DRAFT → campaña DRAFT → creativos DRAFT. Si falla, limpia creativos, campaña y grupo, pero **no borra los posts**.
  - `linkedin_agregar_anuncio`, `linkedin_pausar`.
- **`scripts/google_refresh_token.py`**: OAuth loopback + PKCE; con `--ga4` agrega `analytics.readonly`.
- **Seguridad**
  - `.gitignore`, `scripts/revisar_secretos.py` (escáner de llaves; `--historial` revisa git log).
  - `.github/workflows/pruebas.yml`: escáner + pytest.
  - `.claude/settings.json`: `attribution` vacío y `deny` de `.env`, llaves, `railway` y push a main.
- **`tests/test_servicio.py`**: 29 pruebas.

### Variables en Railway (solo nombres; los valores viven solo en Railway como variables selladas)

- **Generales**: `ANTHROPIC_API_KEY`, `SLACK_*`, `MONDAY_API_TOKEN`, `PUBLIC_URL`, `MODO_PRUEBA`, `HOSTS_IMAGENES`, `MONDAY_COLUMNA_NOTAS`, `MONDAY_ESTATUS_AVISO`, `AVISAR_ELEMENTO_NUEVO`, `SLACK_APROBADORES`.
- **Meta**: `META_*`, incluido `META_API_VERSION`.
- **Google Ads**:
  - Secretos: `GOOGLE_ADS_CLIENT_ID`, `GOOGLE_ADS_CLIENT_SECRET`, `GOOGLE_ADS_REFRESH_TOKEN`, `GOOGLE_ADS_DEVELOPER_TOKEN`.
  - Configuración: `GOOGLE_ADS_API_VERSION=v26`, `GOOGLE_ADS_LOGIN_CUSTOMER_ID`, `GOOGLE_ADS_CUENTAS_PERMITIDAS`, `GOOGLE_ADS_PRESUPUESTO_MAX_DIARIO=500`, `GOOGLE_ADS_MONEDA=MXN`.
- **LinkedIn**: `LINKEDIN_ACCESS_TOKEN`, `LINKEDIN_CUENTAS_PERMITIDAS=519998414`, `LINKEDIN_API_VERSION=202610`, `LINKEDIN_PRESUPUESTO_MAX_DIARIO=500`, `LINKEDIN_MONEDA=MXN`.

## 3. Cuentas

| Plataforma | Dato |
|---|---|
| Google Ads | Cuenta 370-169-8329 "Freelan Marketing 2020" · MXN · America/Mexico_City · MCC (login customer id) 224-020-3724 |
| LinkedIn Ads | Cuenta 519998414 "Freelan Marketing" · MXN · ACTIVE · página `urn:li:organization:3644328` · México `urn:li:geo:103323778` |
| LinkedIn app | "Freelan Agente de Pauta" · Advertising API **Development Tier aprobado** (máximo 5 cuentas con escritura) · token de 60 días generado el 12 nov 2026, **renovar antes del 8 ene 2027** · scopes: r_ads, rw_ads, r_ads_reporting, r_organization_social, w_organization_social |
| Meta | App `ads_management_test`. Para crear creativos debe estar en **Live** (error 1885183). Pendiente. |
| Otros | GA4 (admin) y HubSpot (CEFAT), con acceso concedido pero sin conectar |

## 4. Estado al 17 nov 2026

- **Meta**: configurado y probado; ya se creó la campaña de prueba. Pendientes:
  - Pasar la app a Live.
  - Lanzar la campaña piloto de Freelan (RevenAI) con el brief simplificado de Majo.
- **Google Ads**: funciona de punta a punta.
  - Campaña de prueba "[PRUEBA-AGENTE] RevenOps con HubSpot · Búsqueda" creada en pausa en la cuenta 8329.
  - Campaña de RevenAI con la landing de Toño al 95% (Majo).
- **LinkedIn Ads**: al 80%.
  - Ya resuelto: conexión ok (`/health/linkedin`), scopes ok, rol en la página ok (las imágenes ya suben).
  - **Bloqueo actual**: error 403 "Your application is not configured to access the related advertiser account(s)". Hay que agregar la cuenta 519998414 en la app: Developer Portal → Products → Advertising API → View Ad Accounts. No requiere token nuevo.
  - El elemento de Monday 13539262705 quedó en "Error". Para reintentar: pasarlo a "Listo para montar", escribir en el mismo hilo de Slack "móntala de nuevo en DRAFT, solo este elemento" y presionar Aprobar.
  - Quedaron 2 posts ocultos sin uso (`urn:li:share:7526769480061014017`, `urn:li:share:7526769497081499648`). No estorban.
- **Prueba de RevenAI en LinkedIn** (decisiones tomadas):
  - Objetivo VISITAS_SITIO.
  - Puja de 90 MXN por clic (sugerida 4.95 USD, con tipo de cambio de 18.60).
  - Presupuesto de 200 MXN diarios (mínimo de LinkedIn: 10 USD), del 16 nov al 15 dic 2026.
  - Sin logo en los artes y paleta provisional.
  - Sin marcas de terceros: se cambió "desde el deal en tu CRM" por "propuesta escrita desde tu conversación real con el cliente".
  - Variante B suavizada a "casi siempre".
  - Con una puja de ~90 MXN, 200 al día dan ~2 clics diarios. Para la campaña real, Majo o Amaya definen el presupuesto. Si pasa de 500 diarios, subir `LINKEDIN_PRESUPUESTO_MAX_DIARIO`.
- **Contexto de RevenAI**:
  - Existen `RevenAI_contexto_sin_ejemplos.md` (para la prueba a ciegas) y `RevenAI_contexto_completo.md` (su sección 10 trae palabras clave y copys de referencia).
  - **No está en el repo**: el bot no lee adjuntos de Slack y hubo que pegarlo como texto.
- **Ebook** `https://blog.freelan.com.mx/ebook-cotizacion-lenta`:
  - Título: "La cotización lenta cuesta más de lo que crees".
  - Es una guía en línea **sin formulario ni descarga**. Sus CTA son "Calcular mi costo", "Leer la guía", "Ver Demo" (RevenAI) y "Agendar diagnóstico".
  - Para medir leads, falta configurar conversiones.

## 5. Pendientes técnicos

Cada uno vive como issue. El estado real está ahí, no aquí.

| # | Tema | Issue |
|---|---|---|
| 1 | Botones de aprobación al bloquear una escritura | #2 |
| 2 | LinkedIn: validar acceso, limpiar posts, puja en USD | #3 |
| 3 | Monday: columna Solicitante (mapeo Slack → Monday) | #4 |
| 4 | Contexto: RevenAI.md, lead magnet, logos | #5 |
| 5 | GA4: `ga4_consultar` y `/health/ga4` | #6 |
| 6 | Google Ads: carga mensual de presupuestos | #7 |
| 7 | Monday: webhooks y apagar tarea horaria | #8 |
| 8 | Agente de análisis de Jorge sin credenciales compartidas | #9 |

## 6. Reglas de trabajo

- **Secretos solo en Railway**: nunca en el repo ni en el chat. No leer `.env`.
- **Commits sin Claude como coautor**: `attribution` vacío en `.claude/settings.json`; no agregar `Co-Authored-By`.
- **Nunca push a `main`**: rama + PR, con CI (escáner de secretos + pytest) en verde.
- Al aplicar zips en la Mac: usar terminal (`unzip -o` / `ditto`), **nunca reemplazar con Finder**, porque borra archivos.
- **Reglas de campañas**:
  - Crear siempre en PAUSADO o DRAFT.
  - No activar ni subir presupuesto sin aprobación explícita de Amaya o de la directora de pautas.
  - Sin precios, métricas inventadas, nombres de clientes ni marcas de terceros en los anuncios.
- No sugerir pausar el trabajo por la hora; seguir mientras David siga trabajando.

## 7. Seguimiento del equipo (sesión del 12 nov)

Minuta completa: https://claude.ai/artifact/9NkvenxuCpzHf5S8x4tGTr

- **Acuerdos**:
  - El agente carga presupuestos mensuales en Meta y valida el gasto el último día hábil del mes.
  - El piloto arranca con 4 clientes; Avándaro entra al final.
  - Los contextos de cliente van en Markdown estándar: identidad, tipografía, colores y buyer persona.
  - El agente de HubSpot arranca desde el discovery.
- **Por definir**: conector propio para presupuestos en Google Ads; usuario maestro de solo lectura para HubSpot.
- **Fechas**:
  - LinkedIn: terminar pruebas, David.
  - 18 nov: sesión técnica de Google Ads y presupuestos, David.
  - 20 nov: presupuestos para 4 clientes, Majo.
  - 30 nov: CGA y RACC, Majo.
