# CLAUDE.md · 00-mkt-agency

Sistema operativo del equipo de marketing. Este archivo define **cómo se trabaja**, no **quién es la marca**: toda la identidad se lee en tiempo de ejecución desde las carpetas de contexto.

---

## 1. Estructura del proyecto

| Ruta | Contenido | Uso |
|---|---|---|
| `_Context/` | Estrategia: posicionamiento, ICP, oferta, pilares, canales, embudo, métricas y reglas para agentes. Archivo base: `_Context/Estrategia.md`. Datos operativos de plataformas (IDs de cuentas, tableros, columnas): `_Context/Cuentas.md` | **Fuente de verdad.** Se lee antes de cualquier entregable. |
| `_BrandKIT/` | Tono, forma de hablar, diseño (colores, tipografías, logo, estilo visual) y foco de marca | Se consulta para voz y para cualquier pieza visual. |
| `_Plantillas/` | Ejemplos de trabajo ya aprobados | Referencia de estructura y nivel de calidad. **No** son fuente de datos. |
| `.claude/agents/` | Definiciones de agentes (un rol por archivo) | Ver sección 4. |
| `.claude/skills/` | Skills reutilizables (flujos de trabajo) | Ver sección 4. |
| `_Clientes/<cliente>/` | Contexto de cada cliente: `Estrategia.md`, `BrandKIT/` y `Cuentas.md`, con la misma estructura que los de la agencia | Para entregables de un cliente, **reemplaza** a `_Context/` y `_BrandKIT/`. |
| `_Entregables/<cliente>/<AAAA-MM>/` | Briefs, copys, diseños, revisiones, reportes y campañas | Los agentes leen y escriben aquí. Para la marca propia, `<cliente>` es `agencia`. |

Si una carpeta está vacía o falta el archivo necesario, **se informa y se pregunta**; no se suple con supuestos.

---

## 2. Reglas críticas

### R1 · Identidad
- Todo entregable sigue la guía de voz definida en `_Context/` (y en `_BrandKIT/` cuando exista).
- Carga **solo** los archivos de contexto adicionales que sean estrictamente relevantes para la tarea. No leas carpetas completas "por si acaso".

### R2 · Agnosticismo de marca
- Prohibido escribir en skills, agentes o este archivo datos de marca: nombre, promesa, colores, tipografías, cifras, clientes, vocabulario, precios, URLs o tono concreto.
- Skills y agentes definen **exclusivamente flujos de trabajo, procesos, entradas, salidas y criterios de calidad**.
- Prueba de cumplimiento: si el skill/agente se copiara a otro proyecto con otra `_Context/`, debe funcionar sin editar una sola línea.

### R3 · Inyección dinámica
- El contexto de marca se extrae **siempre en tiempo de ejecución** desde los archivos, nunca desde memoria, ejemplos previos o texto embebido en el prompt.
- Los skills y agentes referencian **rutas y secciones** (p. ej. "sección de vocabulario de `_Context/Estrategia.md`"), no su contenido.
- Si el contexto cambia, el siguiente entregable debe reflejarlo sin tocar ningún skill ni agente.

### R4 · Arquitectura de agentes
- Cada agente tiene **un solo rol, delimitado**, con entradas y salidas explícitas.
- Prohibido que dos agentes compartan responsabilidad. Si una tarea no encaja en ningún rol, se propone un rol nuevo; no se amplía uno existente.
- Los agentes se comunican mediante entregables (archivos), no asumiendo trabajo del otro.

---

## 3. Protocolo de carga de contexto (cada tarea)

0. **Resolver el contexto:** si el entregable es para la agencia, usar `_Context/` y `_BrandKIT/`; si es para un cliente, usar `_Clientes/<cliente>/`. Si no está claro, preguntar. Si el cliente no tiene carpeta, detener y avisar.
1. **Identificar el tipo de entregable** (post, artículo, email, campaña, propuesta, reporte, pieza visual…).
2. **Leer el archivo `Estrategia.md` del contexto resuelto** — siempre. Respetar sus convenciones de etiquetas (dato público / propuesta / por completar) y sus reglas para agentes.
3. **Cargar selectivamente:**
   - Contenido escrito → secciones de voz y vocabulario + `_BrandKIT/` (tono).
   - Pieza visual → `_BrandKIT/` (diseño).
   - Campaña o pauta → ICP, oferta, canales, embudo y métricas.
   - Cliente específico → contexto del cliente, si existe.
4. **Buscar plantilla** en `_Plantillas/` del mismo tipo; usarla como estructura, no como fuente de datos.
5. **Detectar huecos:** cualquier dato marcado como pendiente o inexistente que el entregable necesite → detener y preguntar.

---

## 4. Arquitectura de agentes y skills

### Convenciones
- **Agentes** (`.claude/agents/<rol>.md`): frontmatter con `name`, `description` (cuándo invocarlo) y `tools` mínimas. Cuerpo con: rol, entradas, salidas, qué **no** hace y archivos de contexto que debe leer.
- **Skills** (`.claude/skills/<flujo>/SKILL.md`): un flujo de trabajo repetible paso a paso. Sin datos de marca; solo rutas a leer.
- Nombres en kebab-case y en español.

### Orquestación
- La sesión principal coordina los flujos: invoca a cada agente en orden, le pasa las rutas de los entregables previos y presenta al usuario los puntos de aprobación.
- Los agentes no se invocan entre sí ni piden aprobación: terminan su entregable, lo guardan en `_Entregables/` y devuelven la ruta.
- Cada flujo completo vive como skill en `.claude/skills/` y define el orden de los agentes.
- Los agentes que usan conectores de plataformas (`analista`, `operador-pauta`, `gestor-solicitudes`) no declaran `tools` para heredar los de la sesión; las acciones de riesgo se bloquean en `.claude/settings.json`.

### Roles base (uno por agente, sin traslapes)

| Agente | Responsabilidad única | Entrada | Salida | No hace |
|---|---|---|---|---|
| `estratega` | Convertir una solicitud en un brief (objetivo, audiencia, pilar, canal, CTA, métrica) | Solicitud + `_Context/` | Brief | No redacta ni diseña |
| `redactor` | Escribir el copy a partir del brief | Brief + voz | Borrador de texto | No define estrategia ni revisa marca |
| `disenador` | Especificar o producir la pieza visual | Brief + copy + `_BrandKIT/` | Pieza o especificación visual | No cambia el mensaje |
| `guardian-marca` | Validar cumplimiento de voz, vocabulario, datos y reglas | Entregable + `_Context/` | Aprobado / lista de cambios | No reescribe; devuelve observaciones |
| `analista` | Medir resultados contra las métricas definidas | Datos de plataformas + métricas + mapa de HubSpot | Reporte (.md) y datos del dashboard (.json) | No ejecuta ni modifica campañas |
| `gestor-solicitudes` | Registrar una solicitud aprobada en el gestor de proyectos (brief en Excel + artes adjuntos, estatus inicial) | Brief, copy y artes aprobados + `Cuentas.md` | Elemento en el gestor de proyectos | No crea campañas ni mueve el estatus más allá del inicial |
| `operador-pauta` | Preparar campañas en plataformas, en borrador, y aplicar cambios aprobados | Brief + creativos aprobados, o solicitud de cambio aprobada | Campaña en pausa o cambio aplicado | No activa ni gasta presupuesto sin aprobación humana |

Antes de crear un agente nuevo, verificar que su responsabilidad no esté cubierta por uno existente.

### Skills disponibles

| Skill | Flujo |
|---|---|
| `pieza-contenido` | estratega → redactor → disenador (si es visual) → guardian-marca → aprobación humana |
| `editar-campana` | estado actual → redactor / disenador (si hay material nuevo) → guardian-marca → plan antes → después → aprobación humana → gestor-solicitudes (arte a Monday) → operador-pauta (modo edición) |
| `analizar-campanas` | analista (Meta + Monday + HubSpot, solo lectura) → JSON + resumen → dashboard HTML |
| `campana-meta` | estratega (brief + datos de pauta) → redactor → disenador (PNG) → guardian-marca → aprobación humana → gestor-solicitudes (Monday) → revisión humana → montaje en borrador |

### Plantilla de brief
Todo brief sigue `_Plantillas/brief.md`. Es el contrato entre agentes.

### Flujo estándar
```
Solicitud → estratega (brief) → redactor / disenador → guardian-marca → aprobación humana → publicación/activación
                                                                                         ↓
                                                                                   analista (medición)
```

---

## 5. Puertas de calidad (antes de entregar)

- [ ] Se leyó el contexto vigente en esta ejecución (no de memoria).
- [ ] Voz, tono y vocabulario permitidos/prohibidos verificados contra `_Context/`.
- [ ] Ninguna cifra, testimonio o nombre de cliente inventado; cada cifra con fuente y periodo.
- [ ] Clientes mencionados solo con autorización confirmada.
- [ ] Un solo llamado a la acción por pieza.
- [ ] Nombre de archivo según la convención definida en `_Context/`.
- [ ] Marcado como **pendiente de aprobación humana**: nada se publica, envía ni activa sin ella.

---

## 6. Seguridad y datos

- No guardar en este proyecto claves de API, tokens, credenciales ni bases de datos con datos personales de clientes. `.gitignore` excluye `.env`, `.mcp.json` y carpetas `credenciales/`.
- `.claude/settings.json` bloquea la lectura de archivos de credenciales y la activación de campañas, y pide confirmación antes de crear campañas.
- Las integraciones (CRM, pauta, gestión de proyectos) se usan en modo lectura salvo instrucción explícita; cualquier acción que gaste presupuesto o sea visible al exterior requiere confirmación.

---

## 7. Mantenimiento de este archivo

- Cambios de marca → se editan en `_Context/` o `_BrandKIT/`, **nunca aquí**.
- Cambios de proceso, roles o reglas → se editan aquí.
- Al agregar un agente o skill, actualizar la tabla de la sección 4.
