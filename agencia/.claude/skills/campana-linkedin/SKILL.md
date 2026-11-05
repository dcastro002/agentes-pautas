---
name: campana-linkedin
description: Flujo completo para preparar una campaña de LinkedIn Ads (contenido patrocinado de imagen única, segmentación B2B por cargo, seniority, industria y tamaño de empresa) desde una solicitud hasta dejarla registrada en Monday con brief y artes, lista para revisión humana; después se monta en borrador. Usar cuando se pida crear, preparar o solicitar una campaña o pauta en LinkedIn, o con /campana-linkedin.
---

# Flujo: campaña de LinkedIn

La sesión principal coordina este flujo. Los agentes no se llaman entre sí: cada uno recibe rutas de archivos y devuelve rutas de archivos. Nada se publica ni se gasta: la campaña queda **en borrador** (DRAFT) y una persona la lanza en Campaign Manager.

Esta versión cubre **contenido patrocinado de imagen única** con objetivo de visitas al sitio, interacción o reconocimiento. Carrusel, video, documentos, Lead Gen Forms, mensajes y eventos no se crean aquí: si se piden, avisar que no están soportados todavía.

## Requisitos
- En el servidor: las herramientas `linkedin_*`. En Claude Code no hay conector de LinkedIn que cree campañas: este flujo se corre desde el servidor (Slack o Monday).
- `python3 -c "import openpyxl, PIL"` funciona y hay Chrome o Chromium para los artes.

## Entrada
La solicitud. Si no dice para qué cliente es, preguntar: "¿Es para la agencia o para un cliente?".

## Pasos

### 1. Resolver contexto
Aplicar el paso 0 de la sección 3 de `CLAUDE.md`. Leer el archivo de estrategia y `Cuentas.md` del contexto resuelto (sección LinkedIn Ads). Si falta la sección o la cuenta, detenerse y avisar.

### 2. Brief, audiencia y datos de pauta
Invocar al agente `estratega` con la solicitud, el cliente y el tipo de entregable "campaña LinkedIn". En LinkedIn la audiencia es profesional, así que el estratega la traduce del ICP de la estrategia a **facetas de LinkedIn**:
- **Cargos** (o, si son demasiado específicos, **funciones** + **seniority**).
- **Industrias** y **tamaño de empresa**.
- **Exclusiones** cuando hacen falta (por ejemplo, funciones que nunca compran).
- Ubicación.

Después, la sesión principal convierte cada valor a su **URN** con `linkedin_consultar`:
- Ubicaciones, cargos, industrias, habilidades: `ruta=adTargetingEntities`, `consulta=q=typeahead&facet=urn%3Ali%3AadTargetingFacet%3A<faceta>&query=<texto>` (facetas: `locations`, `titles`, `industries`, `skills`).
- Seniority, funciones, tamaños de empresa: `consulta=q=adTargetingFacet&queryVersion=QUERY_USES_URNS&facet=urn%3Ali%3AadTargetingFacet%3A<faceta>` (facetas: `seniorities`, `jobFunctions`, `staffCountRanges`).
- Si un valor no aparece, proponer el más cercano y preguntar. Nunca inventar un URN.
- Guardar el nombre legible de cada URN en `segmentacion_nombres` para el Excel de revisión.
- LinkedIn necesita **al menos 300 personas** en la audiencia. Si la combinación es muy estrecha, avisarlo y proponer ampliar.

Datos de pauta. Lo que no venga en la solicitud se pregunta en un solo mensaje; para los opcionales, proponer el valor por defecto entre paréntesis:

| Dato | Campo JSON | Valores |
|---|---|---|
| Objetivo | `objetivo` | (VISITAS_SITIO) · INTERACCION · RECONOCIMIENTO |
| Presupuesto diario | `presupuesto_diario` | En la moneda de la cuenta (`Cuentas.md`), debajo del tope |
| Fechas | `inicio`, `fin` | AAAA-MM-DD; inicio hoy o después |
| Puja | `puja.tipo`, `puja.monto` | (CPC) o CPM. Monto: consultar la sugerida con `linkedin_consultar` → `adBudgetPricing` y proponerla |
| Red de audiencia de LinkedIn | `red_de_audiencia` | (false): solo dentro de LinkedIn |
| Número de anuncios | `anuncios` | (2) · máximo 10 |
| URL de destino | `url` | https://, con UTM: `utm_source=linkedin&utm_medium=paid&utm_campaign=<tema>` |

**Punto de aprobación 1:** mostrar en pocas líneas objetivo, audiencia (facetas con sus nombres legibles), mensaje clave, CTA, presupuesto, puja y fechas. Continuar solo con confirmación.

### 3. Copy
Invocar al agente `redactor` con la ruta del brief. Por anuncio:
- **Texto introductorio:** lo importante en los primeros **150 caracteres**, que es lo que se ve antes de "ver más". Máximo 600.
- **Título:** hasta **70 caracteres** recomendados (máximo 200).
- **Botón (CTA):** uno de Más información (LEARN_MORE) · Registrarse (SIGN_UP) · Inscribirse (REGISTER) · Descargar (DOWNLOAD) · Suscribirse (SUBSCRIBE) · Solicitar demo (REQUEST_DEMO) · Ver más (SEE_MORE).
- Tono profesional según la sección de voz de la estrategia, hablándole al cargo de la audiencia.

### 4. Artes
Invocar al agente `disenador` con las rutas del brief y del copy, pidiendo **PNG por anuncio en 1200×627 (horizontal)**, o **1080×1080** si la persona lo pide. Texto en imagen breve; el mensaje va en el texto introductorio.

### 5. Revisión de marca
Invocar al agente `guardian-marca` con copy, PNG y brief.
- **REQUIERE CAMBIOS:** volver al paso 3 o 4. Máximo 2 vueltas; a la tercera, presentar las observaciones y preguntar cómo seguir.
- **APROBADO PARA REVISIÓN HUMANA:** continuar.

### 6. Armar y validar el JSON
Escribir `_Entregables/<cliente>/<AAAA-MM>/<AAAA-MM-DD>_campana_linkedin_<tema>.json`. `cuenta` sale de `Cuentas.md`:
```json
{
  "plataforma": "LinkedIn",
  "cuenta": "<ID de la cuenta de LinkedIn en Cuentas.md>",
  "nombre": "<nombre de la campaña, con el prefijo de Cuentas.md si aplica>",
  "objetivo": "VISITAS_SITIO",
  "presupuesto_diario": 300,
  "puja": {"tipo": "CPC", "monto": 45},
  "inicio": "AAAA-MM-DD", "fin": "AAAA-MM-DD",
  "red_de_audiencia": false,
  "segmentacion": {
    "ubicaciones": ["urn:li:geo:<id>"],
    "seniority": ["urn:li:seniority:<id>"],
    "funciones": ["urn:li:function:<id>"],
    "industrias": ["urn:li:industry:<id>"],
    "tamano_empresa": ["urn:li:staffCountRange:(<de>,<a>)"],
    "excluir": {"funciones": ["urn:li:function:<id>"]}
  },
  "segmentacion_nombres": {"urn:li:geo:<id>": "<nombre legible>"},
  "anuncios": [
    {"texto": "...", "titulo": "...", "cta": "LEARN_MORE", "url": "https://...", "archivo": "<nombre exacto del PNG>"}
  ]
}
```
Validarlo y generar el Excel de revisión:
`python3 .claude/skills/campana-linkedin/scripts/brief_linkedin.py <campana.json> <..._campana_linkedin_<tema>.xlsx>`
Si hay errores, corregirlos con quien corresponda (redactor o estratega) y volver a validar. Los avisos de longitud se presentan en la aprobación.

### 7. Aprobación final
**Punto de aprobación 2:** presentar los anuncios (texto con su número de caracteres, título, botón), los PNG (rutas), la audiencia con nombres legibles, presupuesto, puja y fechas. Indicar que todavía no se ha registrado nada en Monday ni en LinkedIn. Registrar quién aprobó y cuándo.

### 8. Registrar en Monday
Invocar al agente `gestor-solicitudes` con el JSON, el Excel, los PNG y la aprobación. Adjunta el JSON y el Excel en la columna **Brief** y los PNG en **Artes**. Estatus inicial de `Cuentas.md`.

### 9. Entrega
- Link al elemento de Monday y su estatus (el inicial).
- Siguiente paso, tal cual:
  > Revisa el elemento en Monday. Cuando esté bien, pásalo a "Listo para montar": el agente lo monta en LinkedIn **en borrador** y una persona lo lanza en Campaign Manager.

## Montaje (cuando la persona lo aprueba)
Lo hace la sesión principal siguiendo `_Pruebas/agente-pautas-linkedin.md`. Si falla a la mitad, la herramienta borra el grupo y la campaña que quedaron en borrador.

## Reglas
- Si ya hay entregables de la misma campaña en `_Entregables/`, preguntar si se reutilizan o se rehacen. Antes de decidir, consultar el elemento en Monday por ID y por nombre.
- No saltar al guardián de marca.
- No registrar nada en Monday sin la aprobación del paso 7.
- No crear nada en LinkedIn dentro de este flujo hasta que la persona pase el elemento a "Listo para montar" o lo apruebe en Slack.
- Nunca asignar en Monday etiquetas o estatus que disparen tareas automáticas (ver `Cuentas.md`).
- Si en cualquier paso falta un dato, detenerse y preguntar.
