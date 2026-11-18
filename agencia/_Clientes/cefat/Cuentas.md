# Cuentas · CEFAT

> Datos operativos de plataformas de CEFAT: IDs de cuentas, tableros y reglas de cuenta. Los leen `gestor-solicitudes`, `operador-pauta` y `analista`.
> Sin contraseñas, tokens ni claves. Si un dato está como **[Completar]** y la tarea lo necesita, el agente se detiene y pregunta.
> Fuente: contexto maestro de CEFAT (Freelan, 2026-11-13). **Aprobador de CEFAT:** Jorge Rodríguez (Freelan).

## Monday · tablero de solicitudes de pauta
- **Tablero:** [Completar · ¿el mismo tablero de la agencia (`_Context/Cuentas.md`) o uno propio de CEFAT?]
- **Si se usa el tablero de la agencia:** columna Cliente = `CEFAT`; columnas, índices de estatus y reglas de etiquetas iguales a las de `_Context/Cuentas.md`.

## Meta Ads
- **Cuenta publicitaria:** `act_1922847738064807` · "CEFAT" · **moneda USD**
- **Business Manager:** Azteca · 984691601549422
- **Página de Facebook:** [Completar · ID de la página /CEFAT]
- **Instagram:** [Completar · ID de la cuenta @azteca_cefat ligada]
- **Píxel:** [Completar · ID] · eventos: `PageView` en landings A y B; `Lead` en el clic al botón de WhatsApp
- **Objetivo principal:** Click-to-WhatsApp vía ManyChat, con `ref` único por anuncio (ver `Estrategia.md` §7)
- **Tope de prueba:** [Completar · en USD diarios y totales]

> ⚠️ **Cuenta compartida con TV Azteca.** La cuenta tiene campañas que no son de CEFAT (boxeo, Azteca Deportes, RevisaCentral, DAZN, Azteca 7).
> - **Solo crear, leer, editar o reportar** campañas cuyo nombre empiece con `CEFAT_` o `Cefat_` (y la del typo `CEFTA_Tráfico_Papás_Fase3`).
> - **Toda campaña nueva** lleva el prefijo `CEFAT_` (nomenclatura en `Estrategia.md` §8).
> - Nunca pausar, editar ni sumar al gasto de CEFAT las demás campañas. Si una acción toca una campaña sin ese prefijo, detenerse y preguntar.
> - Meta reporta en USD; el cliente ve MXN. Convertir antes de comparar, y decir qué tipo de cambio se usó.

## Google Ads
- **Cuenta:** 3481908807 (348-190-8807) · vinculada a GA4 358743188
- **Moneda y zona horaria:** [Completar · confirmar; el tope del servidor está en MXN]
- **MCC (login customer id):** [Completar · confirmar que la cuenta cuelga del MCC de Freelan 224-020-3724; si no, el servidor no puede entrar]
- **Tipo de campaña soportado:** Red de Búsqueda con anuncios responsivos (skill `campana-google`)
- **Ubicación por defecto:** México `geoTargetConstants/2484` · **Idioma:** español `languageConstants/1003`
- **Prefijo del nombre:** `CEFAT_` (p. ej. `SRC_CEFAT_Carrera` sigue la convención histórica de búsqueda)
- **Tope de prueba:** [Completar · MXN diarios por campaña; el servidor aplica `GOOGLE_ADS_PRESUPUESTO_MAX_DIARIO`]
- **Campañas existentes (jul-2026):** `SRC_CEFAT_Carrera` activa; `SRC_Cefat_Carrera_Foraneos`, `PMax_CEFAT`, `PMAX_Cursos` pausadas. No tocarlas sin solicitud aprobada.

## LinkedIn Ads
- **Cuenta publicitaria:** [Completar · CEFAT no tiene cuenta de LinkedIn Ads en su contexto]
- Si se agrega: darla de alta en la app "Freelan Agente de Pauta" (Developer Portal → Advertising API → View Ad Accounts; máximo 5 cuentas en Development Tier) y en `LINKEDIN_CUENTAS_PERMITIDAS` de Railway.

## TikTok Ads
- Sin conector en el servicio. Solo se lee indirectamente vía GA4.

## HubSpot
- **Portal:** 24405245 · STANDARD · moneda USD. **Verificar el portal antes de leer**: el conector puede apuntar a otro portal (p. ej. el de Freelan).
- **Modo:** solo lectura. Nunca reclasificar contactos ni tocar la atribución.
- **Mapa de propiedades:** [Completar · `_Clientes/cefat/HubSpot-mapa.md`, a partir de la sección 10 del contexto maestro]
- **Lead calificado:** `estado_de_lead_b = "Listo para conversión"` (ver `Estrategia.md` §7)

## GA4
- **Propiedad:** 358743188 ("Cefat GA4") · MXN · zona CDMX
- Filtrar siempre `hostName = cefat.mx`. Excluir spam: `pageTitle "trafficheap.cc"` y `/wp-includes/wp-content/uploads/du`.
- GA4 **no ve** Click-to-WhatsApp de Meta: nunca usarlo para comparar Meta vs. Google.
