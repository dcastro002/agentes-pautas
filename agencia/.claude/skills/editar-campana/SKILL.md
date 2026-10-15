---
name: editar-campana
description: Flujo para editar una campaña de Meta Ads que ya se subió (cambiar, agregar o quitar artes, copys o anuncios; ajustar presupuesto o fechas) con aprobación humana y sin activar nada. Usar cuando se pida editar, corregir, cambiar artes o anuncios de una campaña existente, o con /editar-campana.
---

# Flujo: editar campaña existente

La sesión principal coordina este flujo. Nada se activa: si un anuncio estaba activo, su reemplazo queda en pausa y una persona lo activa en Ads Manager.

## Entrada
- Qué campaña: nombre o ID del elemento de Monday, o ID de la campaña en Meta.
- Qué cambiar, en palabras de la persona.
- Si hay arte nuevo: la ruta del archivo, o pedir que se genere.

Si no está claro cuál campaña o qué cambio, preguntar antes de leer nada más.

## Tipos de cambio
| Cambio | Cómo se hace en Meta |
|---|---|
| Cambiar arte o copy de un anuncio | **El mismo anuncio (mismo ID).** El creativo no se edita: se crea uno nuevo con el conector y se asigna al anuncio existente con `scripts/asignar_creativo.py` (API de Meta directa; el conector no permite este cambio). Si no hay token o Meta lo rechaza: detenerse y ofrecer (a) hacerlo a mano en Ads Manager con los pasos de abajo o (b) anuncio nuevo + retirar el anterior, solo con aprobación |
| Agregar un anuncio | Creativo nuevo → anuncio nuevo en el mismo conjunto, en pausa |
| Quitar un anuncio | Pausar o archivar el anuncio. No se borran imágenes ni creativos |
| Presupuesto o fechas | Solo si la persona lo pide explícitamente; mostrar el monto antes y después en MXN y en centavos |
| Segmentación | Solo si la persona lo pide explícitamente; avisar que reinicia el aprendizaje |

## Pasos

### 1. Resolver contexto y campaña
Aplicar el paso 0 de la sección 3 de `CLAUDE.md` y leer `Cuentas.md`. Localizar la campaña: si viene de Monday, leer el elemento (link a campaña y notas con los IDs); si viene de Meta, buscar el elemento de Monday con ese link. Si no hay elemento en Monday, avisar y preguntar si se continúa sin registro.

### 2. Estado actual ("antes")
Leer en Meta, solo lectura, la campaña, sus conjuntos y anuncios: nombre, estatus, presupuesto, fechas, creativo de cada anuncio (texto, título, CTA, imagen). Presentarlo en una tabla corta.

### 3. Material nuevo (si el cambio lo requiere)
- **Copy nuevo:** agente `redactor` con el brief original y el cambio pedido.
- **Arte nuevo generado:** agente `disenador` (PNG con la misma medida del original).
- **Arte nuevo entregado por la persona:** usar ese archivo tal cual.
- Pasar el material nuevo por `guardian-marca`. Máximo 2 vueltas.

### 4. Plan de cambios
Presentar el plan **antes → después**, una fila por cambio, con la herramienta que se usará. Indicar qué anuncios quedarán en pausa y que nada se activará.

**Punto de aprobación:** continuar solo con confirmación explícita. Registrar quién aprobó y cuándo.

### 5. Arte disponible por URL
Si hay arte nuevo, invocar a `gestor-solicitudes` para adjuntarlo a la columna Artes del **mismo** elemento de Monday (sin quitar los anteriores) y obtener su `public_url` justo antes del paso 6.

### 6. Aplicar en Meta
Invocar a `operador-pauta` en modo edición con: IDs, plan aprobado, `public_url` de cada arte nuevo y la aprobación.

**Cambiar arte o copy del mismo anuncio** (lo hace la sesión principal, no un subagente, porque pide permisos):
1. El operador crea el creativo nuevo con el conector (mismo texto, título, CTA, URL y página que el creativo actual, salvo lo que se pidió cambiar) y devuelve su ID.
2. Simulación: `python3 .claude/skills/editar-campana/scripts/asignar_creativo.py --ad <ID_ANUNCIO> --creative <ID_CREATIVO> --dry-run`
3. Aplicar: el mismo comando sin `--dry-run`. El script verifica que el anuncio quedó con el creativo nuevo y con el mismo estatus.
4. Si falta `META_ACCESS_TOKEN`, detenerse y explicar cómo definirlo; nunca pedir el token en el chat ni guardarlo en archivos.

**Si no se puede por API, pasos en Ads Manager para la persona:** abrir el anuncio → Editar → en "Contenido multimedia" cambiar la imagen por el archivo nuevo → revisar texto y CTA → Publicar los cambios (el anuncio sigue en pausa si lo estaba).

### 7. Registrar
- En Monday, agregar a Notas del agente: fecha, cambio aplicado, IDs nuevos (creativos y anuncios), quién aprobó y qué quedó en pausa. No cambiar el estatus del elemento.
- Guardar el reporte `_Entregables/<cliente>/<AAAA-MM>/<AAAA-MM-DD>_campana_<tema>_edicion.md`.

### 8. Entrega
Mostrar el antes → después verificado en Meta, los IDs nuevos y, si algo quedó en pausa, el aviso: "Este anuncio quedó en pausa; actívalo en Ads Manager cuando lo revises".

## Reglas
- Para cambiar arte o copy se actualiza siempre el **mismo anuncio**. Crear un anuncio nuevo solo es plan B, con aprobación explícita, y siempre retirando el anterior en el mismo plan para no dejar anuncios de más.
- Antes de proponer el plan, revisar que el arte nuevo tenga la misma proporción que el anterior (ej. 1080×1080). Si no, avisarlo en el plan.
- Nunca enviar un estatus `ACTIVE`, ni siquiera con una herramienta de edición.
- No borrar campañas, conjuntos, creativos ni imágenes.
- No cambiar presupuesto, fechas ni segmentación si no se pidió.
- Un cambio a la vez: si uno falla, detenerse y reportar qué sí se aplicó.
