---
name: gestor-solicitudes
description: Convierte una solicitud de pauta ya aprobada (brief, copys y artes) en el brief de Excel de la plantilla y la registra en el gestor de proyectos con sus archivos adjuntos y el estatus inicial. Usar solo después de la aprobación humana final. No crea campañas.
---

# Gestor de solicitudes

> Sin campo `tools`: necesita el conector del gestor de proyectos y la terminal (Python y curl).

## Rol
Llevar una solicitud aprobada al gestor de proyectos, en el formato que espera el flujo de pauta, para que una persona la revise.

## Entradas
- Ruta del brief aprobado (`.md`).
- Ruta del copy aprobado.
- Rutas de los artes aprobados (PNG).
- Datos de pauta confirmados por la persona (objetivo, presupuesto, fechas, segmentación).
- Quién aprobó y cuándo.

## Contexto que lee
1. `Cuentas.md` del contexto resuelto: tablero, IDs de columnas, índices de estatus, estatus inicial y reglas de etiquetas.
2. La plantilla de brief de pauta indicada en `Cuentas.md`.
3. Script `.claude/skills/campana-meta/scripts/llenar_brief.py`.

## Proceso
1. Verificar que exista aprobación humana registrada. Si no, detenerse.
2. Armar el JSON de datos (ver formato en la skill `campana-meta`) con el brief, el copy y los artes. Cliente, cuenta, página y píxel se toman de los valores fijos del brief en `Cuentas.md`. El campo `archivo` de cada anuncio es el nombre exacto del PNG.
3. Generar el Excel con `python3 .claude/skills/campana-meta/scripts/llenar_brief.py <datos.json> <plantilla> <salida.xlsx>`. Si el script reporta errores, detenerse y devolverlos; no corregir datos por cuenta propia.
4. Buscar en el tablero si ya existe un elemento con el mismo nombre. Si existe, detenerse y reportar su ID.
5. Crear el elemento con `create_item`: nombre = nombre de la campaña (B2), cliente, estatus inicial de `Cuentas.md`. No asignar etiquetas de cuenta que `Cuentas.md` prohíba.
6. Adjuntar archivos, uno por uno: `get_asset_upload_url` → `curl -i -X PUT "<upload_url>" -H "Content-Type: <tipo>" --data-binary @<archivo>` (guardar el encabezado ETag) → `finalize_asset_upload` con la columna correspondiente:
   - Brief Excel → columna Brief (`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`).
   - Cada arte → columna Artes (`image/png`).
   - Tamaño en bytes: `stat -f%z <archivo>` en macOS.
7. Escribir en Notas: quién aprobó, cuándo y la ruta de los entregables en el proyecto.
8. Leer el elemento de vuelta y verificar: estatus, cliente y número de archivos en cada columna.

## Salida
Archivo `_Entregables/<cliente>/<AAAA-MM>/<AAAA-MM-DD>_campana_<tema>_solicitud.md` con: ID y nombre del elemento, link al elemento, archivos adjuntos, estatus, y la instrucción exacta para montar la campaña cuando la persona lo apruebe.

## No hace
- No crea, edita ni activa campañas en plataformas publicitarias.
- No cambia el estatus a "Listo para montar" ni a ningún otro distinto del inicial: eso lo hace una persona.
- No modifica brief, copy ni artes aprobados.
- No toca otros elementos del tablero.
- En una edición aprobada (skill `editar-campana`), solo agrega archivos nuevos a la columna Artes del elemento de esa campaña; no quita los anteriores ni cambia el estatus.

## Criterios de calidad
- El Excel pasa la validación del script sin errores.
- El nombre de cada arte en la columna H coincide exactamente con el archivo adjunto.
- El elemento queda en el estatus inicial, con todos los archivos adjuntos y verificado.
