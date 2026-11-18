# Diseño · BrandKIT · CEFAT

> Identidad visual de CEFAT. La leen el diseñador y el guardián de marca. El tono de voz vive en `../Estrategia.md` (sección 2).
> Origen: contexto maestro de CEFAT (2026-11-13), basado en el design brief de la landing `cefat-landing-actoral-2026`.

## Colores

| Rol | Hex | Uso |
|---|---|---|
| Fondo | #000000 | Negro absoluto |
| Superficie | #111111 / #1A1A1A | Secciones y placeholders |
| **Acento — Rojo CEFAT** | **#C8102E** | Solo en palabras de énfasis: máximo 4 por titular |
| Texto principal | #FFFFFF | |
| Texto secundario | #999999 | |
| Bordes | #222222 | |

### Reglas de color
- Fondo negro siempre; el rojo es acento, no fondo.
- Rojo solo en palabras de énfasis (máximo 4 por titular).

## Tipografías
- **Montserrat** — display en peso 800; cuerpo en peso regular.

## Logo
- [Completar · subir los archivos a `logos/` (positivo, negativo e ícono) y confirmar reglas de uso]

## Estilo visual
- Estética **cine / set**: negro, rojo, luces, claqueta, cámara encendida.
- Subtítulos siempre en video (quemados o automáticos).

| Tipo de asset | Credibilidad | Regla |
|---|---|---|
| Grabación real de egresados o alumnos | Máxima | Insustituible; testimonial sin guion, a cámara |
| Grabación real de foros | Máxima | Preferir siempre |
| Video o imagen con IA | Media | Solo atmósfera; **nunca presentarla como los foros reales** |
| Diseño gráfico / objeto simbólico (reflector, cámara, micrófono) | Alta | Ideal para papás y retargeting |

## Formatos frecuentes
| Plataforma | Formato | Medidas |
|---|---|---|
| Instagram / Facebook Stories y Reels | Vertical 9:16 (obligatorio) | 1080×1920 |
| TikTok | Vertical 9:16 (obligatorio) | 1080×1920 |
| Instagram | Post | 1080×1350 |
| Meta Ads | Imagen | 1080×1080 y 1080×1920 |

## Tokens para HTML y SVG
```css
:root{
  --cefat-fondo:#000000; --cefat-superficie:#111111; --cefat-superficie-2:#1A1A1A;
  --cefat-rojo:#C8102E;
  --cefat-texto:#FFFFFF; --cefat-texto-2:#999999; --cefat-borde:#222222;
  --cefat-fuente:'Montserrat', Arial, Helvetica, sans-serif;
}
```
