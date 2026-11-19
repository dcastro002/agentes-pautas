# Cuentas · Agencia

> Datos operativos de plataformas: IDs de cuentas, tableros y columnas. Los leen `gestor-solicitudes` y `operador-pauta`.
> Sin contraseñas, tokens ni claves. Si un dato no está, el agente se detiene y pregunta.

## Monday · tablero de solicitudes de pauta
- **Tablero:** 18434029216 · "[PRUEBA-AGENTE] Requerimientos de Pauta"
- **Columnas:**
  | Columna | ID | Tipo |
  |---|---|---|
  | Nombre | `name` | name |
  | Estatus agente | `color_mm7vt5cg` | status |
  | Cuenta del agente | `color_mm7vqz13` | status |
  | Cliente | `text_mm7v5f5m` | text |
  | Brief (plantilla) | `file_mm7v5nwf` | file |
  | Artes | `file_mm7vag3e` | file |
  | Link a campaña | `link_mm7v50k2` | link |
  | Notas del agente | `long_text_mm7vmg76` | long_text |
  | Solicitante | `multiple_person_mm7vwycn` | people |
- **Estatus agente (índice):** Nuevo 17 · Listo para montar 7 · En proceso (agente) 0 · Borrador listo 4 · Falta info 9 · Error 2 · Activa 1
- **Cuenta del agente (índice):** Prueba 152 · Producción 107
- **Estatus inicial al registrar una solicitud:** Nuevo (17)
- **Etiqueta de cuenta al registrar:** ninguna (dejar vacía). Nunca asignar "Prueba" ni "Producción": esas etiquetas las toman tareas automáticas.
- **Prefijo obligatorio del nombre en este tablero:** `[PRUEBA-AGENTE]`

## Meta Ads
- **Cuenta publicitaria:** 603185293355269 · Freelan_México_2022 · MXN
- **Página:** 709010129143048 · Freelan Marketing
- **Píxel:** 1967777630139214 · Píxel de Freelan_México_2018
- **Instagram:** sin cuenta ligada
- **Presupuesto diario mínimo de la cuenta:** $18.25 MXN
- **Tope de prueba:** $500 MXN diarios o $10,000 MXN totales

## Google Ads
- **Cuenta:** 3701698329 (370-169-8329) · Freelan Marketing 2020 · moneda MXN · zona horaria America/Mexico_City
- **MCC (login customer id):** 2240203724 (224-020-3724) · Freelan Marketing
- **Tipo de campaña soportado:** Red de Búsqueda con anuncios responsivos (skill `campana-google`)
- **Tope de prueba:** $500 MXN diarios por campaña (también lo aplica el servidor)
- **Ubicación por defecto:** México `geoTargetConstants/2484` · **Idioma:** español `languageConstants/1003`
- **Brief en Monday:** JSON de la campaña + Excel de revisión en la columna Brief; la columna Artes queda vacía

## LinkedIn Ads
- **Cuenta publicitaria:** 519998414 · Freelan Marketing · moneda MXN · estatus ACTIVE (confirmado con /health/linkedin el 2026-11-12)
- **Página de empresa:** urn:li:organization:3644328 (Freelan), ligada a la cuenta; el servidor la lee de la cuenta. Quien autoriza el token necesita rol de Administrador o Poster de contenido patrocinado en la página
- **Tipo soportado:** contenido patrocinado de imagen única (skill `campana-linkedin`), objetivos VISITAS_SITIO, INTERACCION y RECONOCIMIENTO
- **Tope de prueba:** 500 MXN diarios por campaña (también lo aplica el servidor)
- **Ubicación por defecto:** México · urn:li:geo:103323778
- **Estado al crear:** todo se crea en DRAFT; la activación la hace la directora de pautas en Campaign Manager
- **Token:** vence a los 60 días (generado 2026-11-12); renovar antes del 2027-01-08
- **Brief en Monday:** JSON de la campaña + Excel de revisión en la columna Brief; PNG en la columna Artes

## HubSpot
- **Portal:** [Completar · ID del portal]
- **Mapa de propiedades:** `_Context/HubSpot-mapa.md` (lo propone el analista la primera vez; una persona lo confirma)
- **Definición de lead calificado:** la de `Estrategia.md` (sección 7). Mientras esté pendiente, los reportes salen sin esa métrica.

## Plantilla de brief de pauta
- Archivo: `_Plantillas/brief-pauta-meta.xlsx` (pestaña "Meta", formulario vertical: columna A campo, B valor, C quién lo llena)
- La cuenta (B14) se elige de la lista de la plantilla por su ID: `603185293355269` (Freelan_México_2022)
- Página y píxel no van en el brief: el montaje los toma de este archivo (sección Meta Ads)
