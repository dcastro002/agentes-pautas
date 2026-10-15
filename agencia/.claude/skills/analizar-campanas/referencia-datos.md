# Referencia · datos del dashboard

El analista entrega un archivo JSON con esta estructura. `scripts/armar_dashboard.py` lo valida y lo inserta en `assets/dashboard.html`.

## Estructura

```json
{
  "meta": {
    "cliente": "", "titulo": "Reporte de desempeño", "periodo": "1 ene – 12 oct 2026",
    "cuenta": "Nombre (ID)", "moneda": "MXN", "generado": "12 oct 2026",
    "fuentes": ["Meta Ads", "Monday", "HubSpot"],
    "preparado_por": "<agencia>", "datos_ficticios": false,
    "alcance_total": 0
  },
  "estado": { "nivel": "good|warning|serious|critical", "texto": "" },
  "meses": ["2026-01", "2026-02"],
  "hechos": [
    { "mes": "2026-05", "campana": "", "conjunto": "", "anuncio": "", "objetivo": "",
      "inversion": 0, "impresiones": 0, "clics": 0, "resultados": 0 }
  ],
  "desgloses": [
    { "dimension": "Edad|Género|Ubicación|Dispositivo|Región", "valor": "",
      "inversion": 0, "impresiones": 0, "clics": 0, "resultados": 0 }
  ],
  "monday": {
    "tablero": "Nombre (ID)",
    "orden_estatus": ["Nuevo", "Listo para montar", "En proceso (agente)", "Borrador listo", "Falta info", "Error", "Activa"],
    "requerimientos": [
      { "nombre": "", "cliente": "", "estatus": "", "solicitante": "", "creado": "AAAA-MM-DD", "causa": "" }
    ]
  },
  "leads": [
    { "mes": "2026-05", "canal": "", "campana": "", "etapa": "", "propietario": "", "calificado": true, "cantidad": 1 }
  ],
  "etapas_orden": ["Subscriber", "Lead", "MQL", "SQL", "Opportunity", "Customer"],
  "salud": [
    { "cuenta": "", "estado": { "nivel": "good", "texto": "Activa" }, "pago": { "nivel": "good", "texto": "Con método de pago" },
      "activos_sin_gasto": 0, "con_problemas": 0, "rechazados": 0, "nota": "" }
  ],
  "hallazgos": [
    { "prioridad": "alta|media|baja", "titulo": "", "observacion": "", "accion": "", "impacto": "", "advertencia": "" }
  ],
  "acciones": [ { "que": "", "donde": "", "resultado": "" } ],
  "calidad": [ { "nivel": "good|warning|serious|critical", "titulo": "", "detalle": "" } ],
  "definiciones": [ { "termino": "", "definicion": "" } ]
}
```

## Reglas de llenado

- **Meses** con formato `AAAA-MM`. `meses` lista todos los del periodo, incluidos los que tienen $0.
- **`hechos`** a nivel anuncio × mes. Es lo que permite filtrar: no lo resumas a nivel campaña. Usa los mismos nombres exactos de campaña y anuncio en todas las filas. Números sin formato (`1799.27`, no `"$1,799"`).
- **`resultados`**: 0 si la campaña no optimiza a un resultado; el dashboard oculta las métricas de resultados si ningún anuncio tiene.
- **`alcance_total`**: el alcance del periodo completo a nivel cuenta, o `null` si no se obtuvo.
- **`desgloses`**: periodo completo a nivel cuenta. Si además obtuviste desgloses por mes, campaña o anuncio, agrega esas llaves a cada fila y el dashboard los filtrará.
- **`leads`**: una fila por combinación con `cantidad`. Déjalo vacío (`[]`) si no hay HubSpot; la pestaña se oculta sola.
- **`salud`**: una fila por cuenta revisada. Si los conteos son parciales, dilo en `nota`.
- **Pestañas sin datos** (lista vacía) se ocultan solas; no inventes contenido para llenarlas.
- **`estado.nivel`**: `good` sin advertencias; `warning` con advertencias menores; `serious` si falta un dato relevante; `critical` si las cifras principales no son confiables.
- **`calidad`** y **`definiciones`** siempre van. Define al menos CTR, CPC, CPM, resultado, recomendación y cada estatus de Monday que aparezca.
- **`datos_ficticios`**: `true` solo con datos de prueba.
- Español de México.
