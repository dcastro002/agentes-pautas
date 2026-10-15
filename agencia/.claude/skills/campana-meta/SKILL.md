---
name: campana-meta
description: Flujo completo para preparar una campaña de Meta Ads desde una solicitud hasta dejarla registrada en Monday con brief en Excel y artes, lista para revisión humana; después se monta en borrador sin publicar. Usar cuando se pida crear, preparar o solicitar una campaña o pauta en Meta, o con /campana-meta.
---

# Flujo: campaña de Meta

La sesión principal coordina este flujo. Los agentes no se llaman entre sí: cada uno recibe rutas de archivos y devuelve rutas de archivos. Nada se publica ni se gasta: al final la campaña queda en borrador y una persona la activa en Ads Manager.

## Requisitos (revisar una vez por sesión)
- Conectores de Monday y Meta disponibles (`/mcp`).
- `python3 -c "import openpyxl, PIL"` funciona. Si no: `pip3 install --user openpyxl Pillow`.
- Google Chrome instalado (para renderizar los artes con `scripts/render_png.py`).

## Entrada
La solicitud del usuario. Si no dice para qué cliente es, preguntar: "¿Es para la agencia o para un cliente?".

## Pasos

### 1. Resolver contexto
Aplicar el paso 0 de la sección 3 de `CLAUDE.md`. Confirmar que existen el archivo de estrategia y `Cuentas.md` del contexto resuelto. Si falta alguno, detenerse y avisar.

### 2. Brief y datos de pauta
Invocar al agente `estratega` con la solicitud, el cliente y el tipo de entregable "campaña Meta".

Además del brief, reunir estos **datos de pauta**. Lo que no venga en la solicitud se pregunta en un solo mensaje; para los opcionales, proponer el valor por defecto entre paréntesis:

| Dato | Celda | Valores |
|---|---|---|
| Objetivo | B4 | Conversiones · Tráfico · Awareness · Alcance · Interacción · Ventas por Catálogo |
| Evento (si es Conversiones) | K3 | Lead · Contact · CompleteRegistration · Schedule · SubmitApplication · Purchase · ViewContent |
| Presupuesto en MXN y tipo | B8, K2 | Diario o Total |
| Fechas de inicio y fin | B6, B7 | AAAA-MM-DD; inicio hoy o después |
| Geografía | B5 | (México) |
| Edad mínima y máxima | K5, K6 | (25 a 55) |
| Género | K7 | (Todos) · Mujeres · Hombres |
| Intereses | K8 | (Broad (sin intereses)) |
| Ubicaciones | K9 | (Advantage+ (automáticas)) · Facebook e Instagram · Solo Facebook · Solo Instagram |
| Categoría especial | K4 | (Ninguna) · Vivienda · Empleo · Crédito · Temas sociales o política |
| URL de destino | D | Debe empezar con https:// |
| Número de anuncios | filas 11-18 | (2) · máximo 8 |

Revisar contra `Cuentas.md`: presupuesto diario mayor o igual al mínimo de la cuenta y por debajo del tope. Si no, avisar antes de seguir.

**Punto de aprobación 1:** mostrar en pocas líneas objetivo, audiencia, mensaje clave, CTA, presupuesto, fechas y segmentación. Continuar solo con confirmación.

### 3. Copy
Invocar al agente `redactor` con la ruta del brief. Pedir, por anuncio: texto principal (copy), título y CTA. El CTA debe ser uno de: Más información · Comprar ahora · Registrarte · Contactarnos · Enviar mensaje · Descargar · Reservar · Suscribirte · Solicitar hora · Ver más.

### 4. Artes
Invocar al agente `disenador` con las rutas del brief y del copy, pidiendo **imagen final PNG 1080×1080 por anuncio** (formato "Imagen única"). Texto en imagen breve; el copy largo va en el anuncio, no en la imagen.

### 5. Revisión de marca
Invocar al agente `guardian-marca` con el copy, los PNG y el brief.
- **REQUIERE CAMBIOS:** volver al paso 3 o 4. Máximo 2 vueltas; a la tercera, presentar las observaciones y preguntar cómo seguir.
- **APROBADO PARA REVISIÓN HUMANA:** continuar.

### 6. Aprobación final
**Punto de aprobación 2:** presentar los copys listos para leer, los PNG (rutas) y la tabla de datos de pauta. Indicar que todavía no se ha registrado nada en Monday ni en Meta. Registrar quién aprobó y cuándo.

### 7. Registrar en Monday
Invocar al agente `gestor-solicitudes` con las rutas del brief, el copy, los PNG, los datos de pauta y la aprobación.

Formato del JSON que arma para el script:
```json
{
  "cliente": "<B1, valor de Cuentas.md>",
  "nombre": "<nombre de campaña, con el prefijo de Cuentas.md si aplica>",
  "plataforma": "Meta", "objetivo": "Conversiones", "geo": "México",
  "inicio": "AAAA-MM-DD", "fin": "AAAA-MM-DD", "presupuesto": 150,
  "tipo_presupuesto": "Diario", "evento": "Lead", "categoria": "Ninguna",
  "edad_min": 25, "edad_max": 55, "genero": "Todos",
  "intereses": "Broad (sin intereses)", "ubicaciones": "Advantage+ (automáticas)",
  "cuenta": "<K11, de Cuentas.md>", "pagina": "<K12, de Cuentas.md>", "pixel": "<K13, de Cuentas.md>",
  "anuncios": [
    {"copy": "...", "titulo": "...", "cta": "Más información",
     "url": "https://...", "formato": "Imagen única", "archivo": "<nombre exacto del PNG>"}
  ]
}
```

### 8. Entrega
Presentar al usuario:
- Link al elemento de Monday y su estatus (el inicial, no "Listo para montar").
- Archivos adjuntos.
- Siguiente paso, tal cual:
  > Revisa el elemento en Monday. Cuando esté bien, pásalo a "Listo para montar" y corre en Claude Code:
  > `Lee _Pruebas/agente-pautas-borrador.md y ejecútalo tal cual, pero en "Esta ejecución" procesa únicamente el elemento "<nombre exacto>".`
  > La campaña queda en borrador; una persona la activa en Ads Manager.

## Reglas
- Si ya hay entregables de la misma campaña en `_Entregables/`, preguntar si se reutilizan (brief, copy, artes) o se rehacen. Un archivo local de solicitud no prueba que el elemento siga en Monday: antes de decidir, consultarlo en Monday por ID y por nombre. Si ya no existe, retomar desde el paso 7 con los entregables aprobados.
- No saltar al guardián de marca aunque la pieza parezca correcta.
- No registrar nada en Monday sin la aprobación del paso 6.
- No crear campañas en Meta dentro de este flujo: eso ocurre después de la revisión en Monday.
- Nunca asignar en Monday etiquetas o estatus que disparen tareas automáticas (ver `Cuentas.md`).
- Si en cualquier paso falta un dato, detenerse y preguntar.
