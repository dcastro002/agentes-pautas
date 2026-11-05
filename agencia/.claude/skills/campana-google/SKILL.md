---
name: campana-google
description: Flujo completo para preparar una campaña de Google Ads en la Red de Búsqueda (palabras clave y anuncios responsivos) desde una solicitud hasta dejarla registrada en Monday con su brief, lista para revisión humana; después se monta en pausa. Usar cuando se pida crear, preparar o solicitar una campaña o pauta en Google, Google Ads o búsqueda, o con /campana-google.
---

# Flujo: campaña de Google Search

La sesión principal coordina este flujo. Los agentes no se llaman entre sí: cada uno recibe rutas de archivos y devuelve rutas de archivos. Nada se publica ni se gasta: la campaña queda **en pausa** y una persona la activa en Google Ads.

Esta versión cubre **campañas de la Red de Búsqueda** con anuncios responsivos de búsqueda (RSA). Performance Max, Display, Video y Demand Gen no se crean aquí: si se piden, avisar que no están soportados todavía.

## Requisitos
- En el servidor: las herramientas `google_ads_*`. En Claude Code no hay conector de Google Ads que cree campañas: este flujo se corre desde el servidor (Slack o Monday).
- `python3 -c "import openpyxl"` funciona.

## Entrada
La solicitud. Si no dice para qué cliente es, preguntar: "¿Es para la agencia o para un cliente?".

## Pasos

### 1. Resolver contexto
Aplicar el paso 0 de la sección 3 de `CLAUDE.md`. Leer el archivo de estrategia y `Cuentas.md` del contexto resuelto (sección Google Ads). Si falta la sección o la cuenta, detenerse y avisar.

### 2. Brief y datos de pauta
Invocar al agente `estratega` con la solicitud, el cliente y el tipo de entregable "campaña Google Search". Además del brief, el estratega propone:
- **Grupos de anuncios:** de 1 a 5 por campaña, uno por intención de búsqueda distinta (por ejemplo, "software de facturación" y "contador para pymes" van en grupos separados).
- **Palabras clave por grupo:** de 5 a 20, en las palabras que usaría el cliente ideal al buscar, con concordancia **FRASE** o **EXACTA**. **AMPLIA** solo si la persona lo pide. No hay datos de volumen de búsqueda (el planificador de palabras clave no está disponible con el acceso actual): se eligen por criterio del ICP y se dice así en el brief.
- **Negativas:** de campaña (búsquedas que nunca convienen: empleo, gratis, curso, tutorial, PDF, etc., según el ICP) y por grupo si hace falta para que dos grupos no compitan.

Datos de pauta. Lo que no venga en la solicitud se pregunta en un solo mensaje; para los opcionales, proponer el valor por defecto entre paréntesis:

| Dato | Campo JSON | Valores |
|---|---|---|
| Presupuesto diario en MXN | `presupuesto_diario_mxn` | Debajo del tope de `Cuentas.md` |
| Fechas | `inicio`, `fin` | AAAA-MM-DD; inicio hoy o después; fin opcional |
| Estrategia de puja | `estrategia` | (MAXIMIZAR_CLICS) · CPC_MANUAL |
| CPC máximo en MXN | `cpc_max_mxn` | Opcional con MAXIMIZAR_CLICS (tope); obligatorio con CPC_MANUAL |
| Ubicaciones | `ubicaciones` | (México: `geoTargetConstants/2484`). Para estados o ciudades, buscar el ID con `google_ads_consultar` en `geo_target_constant`; si no se encuentra, preguntar |
| Idiomas | `idiomas` | (Español: `languageConstants/1003`) |
| Socios de búsqueda | `red_de_socios_de_busqueda` | (false) |
| Red de Display | `red_display` | (false) |
| URL de destino | `url_final` en cada anuncio | https://, con UTM: `utm_source=google&utm_medium=cpc&utm_campaign=<tema>` |

**Punto de aprobación 1:** mostrar en pocas líneas objetivo, audiencia, grupos con 3 palabras clave de ejemplo cada uno, negativas principales, presupuesto, fechas y puja. Continuar solo con confirmación.

### 3. Anuncios
Invocar al agente `redactor` con la ruta del brief. Pedir, por grupo, **un anuncio responsivo** con:
- **De 8 a 15 títulos de máximo 30 caracteres** (contando espacios). Variados: la palabra clave principal en al menos 2, la propuesta de valor, prueba o diferenciador, y el CTA de la estrategia. Sin repetir títulos.
- **4 descripciones de máximo 90 caracteres.**
- **Ruta visible** (`ruta1`, `ruta2`): máximo 15 caracteres cada una, en minúsculas y sin acentos (por ejemplo `facturacion` / `pymes`).
- Sin signos de exclamación en los títulos, sin MAYÚSCULAS SOSTENIDAS y sin precios ni cifras que la estrategia no respalde: Google los rechaza o la marca los prohíbe.

No hay artes en este flujo: la Red de Búsqueda es solo texto.

### 4. Revisión de marca
Invocar al agente `guardian-marca` con los anuncios y el brief.
- **REQUIERE CAMBIOS:** volver al paso 3. Máximo 2 vueltas; a la tercera, presentar las observaciones y preguntar cómo seguir.
- **APROBADO PARA REVISIÓN HUMANA:** continuar.

### 5. Armar y validar el JSON
Escribir `_Entregables/<cliente>/<AAAA-MM>/<AAAA-MM-DD>_campana_google_<tema>.json` con este formato. `cuenta` sale de `Cuentas.md`:
```json
{
  "plataforma": "Google",
  "cuenta": "<ID de la cuenta de Google Ads en Cuentas.md, sin guiones>",
  "nombre": "<nombre de la campaña, con el prefijo de Cuentas.md si aplica>",
  "presupuesto_diario_mxn": 100,
  "inicio": "AAAA-MM-DD", "fin": "AAAA-MM-DD",
  "estrategia": "MAXIMIZAR_CLICS", "cpc_max_mxn": 25,
  "ubicaciones": ["geoTargetConstants/2484"], "idiomas": ["languageConstants/1003"],
  "red_de_socios_de_busqueda": false, "red_display": false,
  "negativas_campana": ["empleo", "gratis", "curso"],
  "grupos": [
    {"nombre": "<intención de búsqueda>",
     "palabras_clave": [{"texto": "<palabra clave 1>", "concordancia": "FRASE"},
                        {"texto": "<palabra clave 2>", "concordancia": "EXACTA"}],
     "negativas": [],
     "anuncios": [{"titulos": ["...", "...", "..."], "descripciones": ["...", "..."],
                   "url_final": "https://...", "ruta1": "<ruta1>", "ruta2": "<ruta2>"}]}
  ]
}
```
Validarlo y generar el Excel de revisión:
`python3 .claude/skills/campana-google/scripts/brief_google.py <campana.json> <..._campana_google_<tema>.xlsx>`
Si el script reporta errores (títulos largos, faltantes), corregirlos con el redactor y volver a validar. No recortar textos por cuenta propia.

### 6. Aprobación final
**Punto de aprobación 2:** presentar, por grupo: palabras clave, negativas y el anuncio (títulos y descripciones con su número de caracteres), más presupuesto, fechas, puja y ubicaciones. Indicar que todavía no se ha registrado nada en Monday ni en Google Ads. Registrar quién aprobó y cuándo.

### 7. Registrar en Monday
Invocar al agente `gestor-solicitudes` con el JSON, el Excel, el brief y la aprobación. Adjunta **los dos archivos** (JSON y Excel) en la columna **Brief**; la columna Artes queda vacía. Estatus inicial de `Cuentas.md`.

### 8. Entrega
- Link al elemento de Monday y su estatus (el inicial).
- Siguiente paso, tal cual:
  > Revisa el elemento en Monday (el Excel tiene las palabras clave y los anuncios). Cuando esté bien, pásalo a "Listo para montar": el agente lo monta en Google Ads **en pausa** y una persona lo activa.

## Montaje (cuando la persona lo aprueba)
Lo hace la sesión principal siguiendo `_Pruebas/agente-pautas-google.md`. Una sola llamada a `google_ads_montar_busqueda` crea todo o nada: si Google rechaza una pieza, no queda una campaña a medias.

## Reglas
- Si ya hay entregables de la misma campaña en `_Entregables/`, preguntar si se reutilizan o se rehacen. Antes de decidir, consultar el elemento en Monday por ID y por nombre.
- No saltar al guardián de marca.
- No registrar nada en Monday sin la aprobación del paso 6.
- No crear nada en Google Ads dentro de este flujo hasta que la persona pase el elemento a "Listo para montar" o lo apruebe en Slack.
- Nunca asignar en Monday etiquetas o estatus que disparen tareas automáticas (ver `Cuentas.md`).
- Si en cualquier paso falta un dato, detenerse y preguntar.
