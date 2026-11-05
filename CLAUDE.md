# agentes-pauta · reglas para trabajar en este repo

Servicio en Railway (FastAPI + Slack + Claude Agent SDK) que crea campañas de Meta, Google Ads y LinkedIn **en pausa o borrador**, con aprobación humana. La carpeta `agencia/` es el proyecto de marketing que usa el agente; su propio `CLAUDE.md` rige el trabajo de marketing, no el código.

## Seguridad (no negociable)
- **Ningún secreto en el repo.** Tokens, API keys, client secrets y refresh tokens viven SOLO en las variables de Railway. No los escribas en código, pruebas, docs, commits ni mensajes. `.env.example` lleva los nombres de las variables, nunca valores.
- Si necesitas un valor para probar, usa uno falso (`"x"`, `"t"`), como en `tests/`.
- No pidas tokens a la persona ni intentes leerlos de ningún lado. Las pruebas no necesitan red ni credenciales.
- Antes de proponer un commit, corre `python3 scripts/revisar_secretos.py` y `python -m pytest -q tests`.
- No hagas push a `main`. Trabaja en una rama y abre un PR: Railway despliega desde `main`.

## Candados del producto (no debilitarlos sin que la persona lo pida explícitamente)
- No existe forma de activar campañas. Meta: todo en PAUSED. Google: campaña en PAUSED y lo agregado después en PAUSED. LinkedIn: todo en DRAFT; estatus solo PAUSED o ARCHIVED.
- Escrituras solo con aprobación (`ctx.puede_escribir()`), solo cuentas permitidas, topes de presupuesto, `MODO_PRUEBA`.
- `app/config.py` retira los secretos de `os.environ` para que el agente no los vea; `app/runner.py` bloquea red desde la terminal del agente.
- Cualquier cambio en `app/tools/` lleva prueba en `tests/test_servicio.py`.
