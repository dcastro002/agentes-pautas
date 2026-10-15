# Agente de Pauta · Slack 

Servicio para que el equipo cree, suba, edite y analice campañas de Meta **desde Slack**, sin Claude ni Claude Code. Usa los mismos agentes y skills del proyecto (carpeta `agencia/`) con el Claude Agent SDK, y Monday sigue siendo el registro.

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