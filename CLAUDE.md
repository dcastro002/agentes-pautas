# agentes-pauta · reglas para trabajar en este repo

Servicio en Railway (FastAPI + Slack + Claude Agent SDK) que crea campañas de Meta, Google Ads y LinkedIn **en pausa o borrador**, con aprobación humana. La carpeta `agencia/` es el proyecto de marketing que usa el agente; su propio `CLAUDE.md` rige el trabajo de marketing, no el código.

## Seguridad (no negociable)
- **Ningún secreto en el repo.** Tokens, API keys, client secrets y refresh tokens viven SOLO en las variables de Railway. No los escribas en código, pruebas, docs, commits ni mensajes. `.env.example` lleva los nombres de las variables, nunca valores.
- Si necesitas un valor para probar, usa uno falso (`"x"`, `"t"`), como en `tests/`.
- No pidas tokens a la persona ni intentes leerlos de ningún lado. Las pruebas no necesitan red ni credenciales.

## Ramas, commits y PRs
Railway despliega desde `main`, así que lo que entra a `main` sale a producción.

**Ramas**
- Nunca trabajes ni hagas push a `main`. Tampoco `push --force`.
- Una rama por tema, con prefijo y en minúsculas: `feat/…`, `fix/…`, `docs/…`, `chore/…` (ej. `fix/linkedin-acceso-cuenta`).
- Si el tema tiene issue, ponle el número: `fix/3-linkedin-acceso-cuenta`.
- Nunca uses el prefijo `claude/` en ramas.

**Commits**
- Antes de cada commit corre `python3 scripts/revisar_secretos.py` y `python3 -m pytest -q tests`. Si algo falla, no hagas commit.
- Mensaje en español, en imperativo y corto: `LinkedIn: revisar acceso antes de crear posts`. Prefijo opcional con la plataforma o módulo.
- Un commit = un cambio con sentido. No mezcles refactor con funcionalidad.
- Sin coautor de Claude: no agregues `Co-Authored-By` (ya está vacío `attribution` en `.claude/settings.json`).
- Haz commit solo cuando la persona lo pida.

**PRs**
- Abre el PR hacia `main` con `gh pr create`. Título igual que el commit principal.
- Cuerpo: qué cambia, por qué, cómo se probó y `Closes #N` si cierra un issue.
- No menciones a Claude ni IA en títulos o descripciones de PR, ni agregues "Generated with Claude Code".
- Si toca `app/tools/` o los candados del producto, dilo en el PR y señala la prueba nueva.
- Solo se fusiona con CI en verde (escáner de secretos + pytest). No actives auto-merge sin que la persona lo pida.
- Los pendientes viven como issues en GitHub; [`docs/CONTEXTO.md`](docs/CONTEXTO.md) los enlaza.

## Candados del producto (no debilitarlos sin que la persona lo pida explícitamente)
- No existe forma de activar campañas. Meta: todo en PAUSED. Google: campaña en PAUSED y lo agregado después en PAUSED. LinkedIn: todo en DRAFT; estatus solo PAUSED o ARCHIVED.
- Escrituras solo con aprobación (`ctx.puede_escribir()`), solo cuentas permitidas, topes de presupuesto, `MODO_PRUEBA`.
- `app/config.py` retira los secretos de `os.environ` para que el agente no los vea; `app/runner.py` bloquea red desde la terminal del agente.
- Cualquier cambio en `app/tools/` lleva prueba en `tests/test_servicio.py`.
