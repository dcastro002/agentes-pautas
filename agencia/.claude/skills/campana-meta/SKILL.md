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

Además del brief, reunir estos **datos de pauta**. Siguen la plantilla `_Plantillas/brief-pauta-meta.xlsx` (pestaña "Meta"; columna C dice quién llena cada campo). Lo que no venga en la solicitud se pregunta en un solo mensaje; para los opcionales, proponer el valor por defecto entre paréntesis. Las opciones de las listas son las de la plantilla: el script las valida.

| Dato | Celda | Valores |
|---|---|---|
| Cuenta publicitaria | B14 | La de `Cuentas.md` del cliente (debe estar en la lista de la plantilla) |
| Nombre de la campaña | B17 | `Cliente_Objetivo_Producto_MesAño`, con el prefijo de `Cuentas.md` si aplica |
| Plataformas | B18 | (Facebook e Instagram) · Solo Facebook · Solo Instagram · Facebook, Instagram, Messenger y Audience Network |
| Objetivo | B19 | Conversiones · Tráfico · Awareness · Interacción · Alcance (Form Lead Gen Nativo y Mensajes Whatsapp: el servidor todavía no los monta) |
| Fecha y hora de fin | B20 | AAAA-MM-DD HH:MM. Sin fecha de inicio en la plantilla: la campaña inicia cuando una persona la activa |
| Destino de la conversión | B23 | (Sitio web) · Formulario instantáneo · WhatsApp · Messenger · Llamadas · Sitio web y app |
| Evento (si es Conversiones) | B24 | Lead · Purchase · Contact · CompleteRegistration · Schedule · SubmitApplication · ViewContent · AddToCart |
| Conjuntos de anuncios | B26 | (1) y qué se prueba entre ellos |
| Presupuesto por conjunto | B27 | Número en la **moneda de la cuenta** (`Cuentas.md`), **diario** salvo que se pida total. Por debajo del tope |
| Geografía | B28 | País, estado, ciudad o radio |
| Edad | B29 | Ej. 18–22 (con Advantage+ Audience es una sugerencia, no un límite) |
| Pistas de segmentación | B30 | Del solicitante; si no hay, del ICP del contexto |
| Ubicaciones | B31 | (Advantage+ (automáticas)) · Manuales: Feeds · Manuales: Stories y Reels · Manuales: Feeds, Stories y Reels |
| Formato | B35 | Imagen única (Video y Carrusel: el servidor todavía no los monta) |
| CTA | B47 | Lista de la plantilla (ej. Más información, Registrarte, Contactarnos) |
| URL de destino | B48 | Debe empezar con https:// |
| KPI principal | B51 | CPL · CPA · ROAS · CPC · CPM · Volumen de leads · Alcance |

**Defaults de la plantilla (aplicar salvo que la solicitud diga otra cosa):** categoría especial Ninguna · presupuesto **ABO** (por conjunto) · género Todos · **Advantage+ Audience** · segmentación y artes según el contexto del cliente · artes en **3 tamaños** (1:1, 4:5, 9:16) · **3 variantes de copy** por anuncio · todo se sube en pausa.

Revisar contra `Cuentas.md`: presupuesto por conjunto × número de conjuntos por debajo del tope de la cuenta. Si no, avisar antes de seguir.

**Punto de aprobación 1:** mostrar en pocas líneas objetivo, audiencia, mensaje clave, CTA, presupuesto, fechas y segmentación. Continuar solo con confirmación.

### 3. Copy
Invocar al agente `redactor` con la ruta del brief y las instrucciones del solicitante (B43). Pedir **3 variantes** de texto principal (~125 caracteres visibles), de título (máximo 40) y de descripción (máximo 30). El CTA es uno de la lista de la plantilla (B47).

### 4. Artes
Invocar al agente `disenador` con las rutas del brief y del copy, pidiendo cada concepto en **3 tamaños PNG**: 1:1 (1080×1080), 4:5 (1080×1350) y 9:16 (1080×1920), formato "Imagen única". Usa las instrucciones del solicitante (B37) y el texto dentro de la imagen (B38). Texto en imagen breve; el copy largo va en el anuncio.

### 5. Revisión de marca
Invocar al agente `guardian-marca` con el copy, los PNG y el brief.
- **REQUIERE CAMBIOS:** volver al paso 3 o 4. Máximo 2 vueltas; a la tercera, presentar las observaciones y preguntar cómo seguir.
- **APROBADO PARA REVISIÓN HUMANA:** continuar.

### 6. Aprobación final
**Punto de aprobación 2:** presentar los copys listos para leer, los PNG (rutas) y la tabla de datos de pauta. Indicar que todavía no se ha registrado nada en Monday ni en Meta. Registrar quién aprobó y cuándo.

### 7. Registrar en Monday
Invocar al agente `gestor-solicitudes` con las rutas del brief, el copy, los PNG, los datos de pauta y la aprobación.

Formato del JSON que arma para `scripts/llenar_brief.py` (escribe la columna B de la plantilla; la sección 7, salida del agente, queda vacía para el montaje):
```json
{
  "cuenta": "<ID de Cuentas.md, sin act_>",
  "nombre": "<B17, con el prefijo de Cuentas.md si aplica>",
  "plataformas": "Facebook e Instagram", "objetivo": "Tráfico", "fin": "AAAA-MM-DD HH:MM",
  "destino": "Sitio web", "evento": "<solo si es Conversiones>", "formulario_o_whatsapp": "<solo si aplica>",
  "conjuntos": "1 conjunto abierto", "presupuesto_conjunto": 10,
  "geo": "CDMX y Estado de México", "edad": "18–22",
  "pistas_segmentacion": "...", "ubicaciones": "Advantage+ (automáticas)",
  "segmentacion_final": "<la segmentación que se configurará, en palabras>",
  "formato": "Imagen única", "carpeta_assets": "...", "instrucciones_artes": "...", "texto_imagen": "...",
  "variantes": "1 concepto × 3 tamaños", "artes": ["<nombre exacto de cada PNG>"],
  "instrucciones_copy": "...", "textos": ["...", "...", "..."], "titulos": ["...", "...", "..."],
  "descripciones": ["...", "...", "..."], "cta": "Más información", "url": "https://...", "kpi": "CPC"
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
