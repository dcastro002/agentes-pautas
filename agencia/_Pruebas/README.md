# Pruebas

Prompts para probar flujos antes de convertirlos en agentes o skills. No son parte de la arquitectura del proyecto.

| Archivo | Qué hace | Escribe en Meta y Monday |
|---|---|---|
| `agente-pautas-simulacion.md` | Lee Monday y el brief, valida y muestra el plan de la campaña | No |
| `agente-pautas-borrador.md` | Crea campaña, conjunto, creativo y anuncio en Meta **sin publicar ni gastar**, y actualiza Monday a "Borrador listo" | Sí |

**Cómo se corre** (en Claude Code, dentro de este proyecto):
> Lee _Pruebas/agente-pautas-borrador.md y ejecuta sus instrucciones tal cual, usando los conectores de Monday y Meta.

- Nunca activa: `ads_activate_entity` está bloqueado en `.claude/settings.json`. Una persona revisa y activa en Ads Manager.
- Claude Code pide confirmación antes de cada creación en Meta.
- El bloque "Esta ejecución" al final define qué elemento de Monday se procesa. Quítalo para que tome todos los elementos en "Listo para montar" con la etiqueta de cuenta del prompt.
