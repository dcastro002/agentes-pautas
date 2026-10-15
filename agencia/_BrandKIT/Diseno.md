# Diseño · BrandKIT

> Identidad visual de la marca. Lo leen el diseñador y el guardián de marca. El tono de voz vive en `_Context/Estrategia.md` (sección 2) para no duplicarlo.
> Origen: capturas del sitio (inicio y ARA Framework™) y de LinkedIn, 12-oct-2026. Los hex son muestreados de pantalla: **aproximados**, confirmar con el manual de marca o el CSS del sitio antes de imprimir.

## Colores

### Base (fondos oscuros)
| Rol | Hex | Uso |
|---|---|---|
| Azul noche (fondo principal) | #110F28 | Fondo de portadas, hero y piezas para redes |
| Negro de barra | #080612 | Barra de navegación, pie, bloques de máximo contraste |
| Violeta profundo | #1A1235 | Brillo o zona clara del fondo (degradado radial sobre el azul noche) |

### Acción y acentos
| Rol | Hex | Uso |
|---|---|---|
| Azul acción | #294471 | Botón principal (CTA) con texto blanco · contraste 9.7:1 |
| Degradado de acento | #D477C8 → #B47FED → #8F8AF2 | Rosa → violeta → lavanda. Solo en 1 o 2 palabras clave del titular ("inteligencia", "HubSpot.") · contraste ≥ 6.3:1 sobre azul noche |
| Turquesa ARA | #8ED4D6 | Acento de la línea ARA Framework™ y palabra destacada en titulares |
| Turquesa nodo | #AAE5E7 | Puntos y líneas de la red de nodos |
| Fondo ARA | #76B4B8 → #141825 | Degradado diagonal turquesa → azul casi negro (portadas del framework) |
| Verde estado | #84D09A | Punto pequeño de "activo" en etiquetas; nunca como color de marca |

### Texto y fondos claros
| Rol | Hex | Uso |
|---|---|---|
| Titular sobre oscuro | #FFFFFF | Titulares |
| Texto sobre oscuro | #CFCFD5 | Párrafos y subtítulos · contraste 12.1:1 |
| Texto sobre claro | #040817 | Titulares y texto en secciones blancas |
| Fondo claro | #FFFFFF | Secciones de contenido, documentos, propuestas |

### Reglas de color
- Las piezas de marca van sobre fondo oscuro (azul noche) por defecto; el blanco es para documentos y secciones de lectura larga.
- Un solo acento por pieza: degradado **o** turquesa, no ambos.
- El turquesa sobre blanco tiene contraste 1.7:1: solo en titulares de 40 px o más y nunca en texto de lectura. Sobre azul noche no tiene restricción (11.2:1).
- No usar el verde del botón de WhatsApp del sitio como color de marca.

## Tipografías
- **Familia:** Lato (Google Fonts). [Aparente en el sitio · confirmar]
- **Titulares:** Lato Black o Bold (900/700), tamaño grande, interlineado cerrado (~1.1), con una palabra destacada en degradado o turquesa.
- **Texto:** Lato Regular (400), interlineado ~1.5.
- **Botones:** Lato Bold o Semibold, mayúsculas y minúsculas, con flecha al final ("Agenda una Charla Estratégica →").
- **Etiquetas (píldoras):** Lato Bold en MAYÚSCULAS con espaciado amplio ("ARA FRAMEWORK™"), o en tipo oración con ícono ("Autonomous Revenue Architecture").
- **Alternativa segura:** Arial o Helvetica, solo si Lato no está disponible.
- Logotipo "FREELAN": letra propia del logo; no recrearlo con Lato, usar siempre el archivo.

## Logo
- **Construcción:** monograma "F" mayúscula dentro de una roseta de líneas finas entrelazadas (tipo guilloché o espirógrafo), seguido de la palabra **FREELAN** en mayúsculas.
- **Versión negativa:** F y palabra en blanco, roseta en gris claro, sobre fondo oscuro (sitio).
- **Versión positiva:** F y roseta en negro sobre blanco (avatar de LinkedIn).
- **Ícono:** roseta + F sin la palabra, para avatares y favicon.
- Archivos: `_BrandKIT/logos/logo-principal.svg`, `logo-negativo.svg`, `icono.svg` [Completar · subir los SVG]
- Área de protección: [Completar · propuesta: la altura de la "F" alrededor del logo]
- Usos prohibidos: deformar, cambiar colores, aplicar el degradado al logo, ponerlo sobre fondos que reduzcan contraste.

## Estilo visual
- **Fondo:** azul noche con brillo violeta suave y una **red de nodos conectados** (constelación de puntos con líneas finas y halo). En piezas del ARA Framework™, la misma red en turquesa sobre el degradado ARA.
- **Composición:** mucho espacio negativo; titular grande alineado a la izquierda (o centrado en portadas); una idea por pieza.
- **Etiqueta superior:** píldora con borde fino y fondo translúcido encima del titular.
- **Botones:** esquinas ligeramente redondeadas (~4 px). Principal relleno azul acción; secundario solo con borde fino claro y fondo transparente.
- **Sellos de alianza:** HubSpot Diamond y Aircall Silver, pequeños y en una esquina (como en la portada de LinkedIn).
- **Imagen — Sí:** capturas reales de dashboards, flujos y CRM; diagramas de arquitectura; fotos del equipo y de eventos.
- **Imagen — No:** stock genérico, robots, cerebros digitales, manos humanas tocando pantallas.

## Formatos frecuentes
| Plataforma | Formato | Medidas |
|---|---|---|
| LinkedIn | Imagen | 1200×1200 o 1200×627 |
| LinkedIn | Carrusel (PDF) | 1080×1350 |
| LinkedIn | Portada de página | 1128×191 |
| Instagram | Post | 1080×1350 |
| Instagram | Historia o reel | 1080×1920 |
| Meta Ads | Imagen | 1080×1080 y 1080×1920 |
| YouTube | Miniatura | 1280×720 |

## Tokens para HTML y SVG
```css
:root{
  --fl-noche:#110F28; --fl-negro:#080612; --fl-violeta:#1A1235;
  --fl-accion:#294471;
  --fl-acento: linear-gradient(90deg,#D477C8 0%,#B47FED 55%,#8F8AF2 100%);
  --fl-turquesa:#8ED4D6; --fl-nodo:#AAE5E7;
  --fl-ara: linear-gradient(120deg,#76B4B8 0%,#141825 75%);
  --fl-texto-oscuro:#CFCFD5; --fl-texto-claro:#040817; --fl-blanco:#FFFFFF;
  --fl-fuente:'Lato', Arial, Helvetica, sans-serif;
}
```
