---
name: pieza-contenido
description: Flujo completo para crear una pieza de contenido (post, carrusel, artículo, email, anuncio) de la solicitud a la aprobación humana, coordinando estratega, redactor, diseñador y guardián de marca. Usar cuando se pida crear contenido o con /pieza-contenido.
---

# Flujo: pieza de contenido

La sesión principal coordina este flujo. Los agentes no se llaman entre sí: cada uno recibe rutas de archivos y devuelve rutas de archivos.

## Entrada
La solicitud del usuario. Si no dice para qué cliente es, preguntar: "¿Es para la agencia o para un cliente?".

## Pasos

### 1. Resolver contexto
Aplicar el paso 0 de la sección 3 de `CLAUDE.md`. Confirmar que existe el archivo de estrategia del cliente. Si no existe, detenerse y avisar.

### 2. Brief
Invocar al agente `estratega` con la solicitud y el cliente.
- Si el brief trae huecos, presentarlos al usuario en un solo mensaje y esperar respuesta.
- Con las respuestas, pedir al `estratega` que actualice el brief.

**Punto de aprobación 1:** mostrar al usuario objetivo, audiencia, canal, mensaje clave y CTA en 5 líneas. Continuar solo con su confirmación.

### 3. Copy
Invocar al agente `redactor` con la ruta del brief.

### 4. Diseño (solo si la pieza es visual)
Invocar al agente `disenador` con las rutas del brief y del copy.
Si reporta que el copy no cabe, volver al paso 3 con esa observación.

### 5. Revisión de marca
Invocar al agente `guardian-marca` con las rutas del entregable y del brief.
- **REQUIERE CAMBIOS:** volver al paso 3 o 4 con la revisión. Máximo 2 vueltas; a la tercera, presentar al usuario las observaciones pendientes y preguntar cómo seguir.
- **APROBADO PARA REVISIÓN HUMANA:** continuar.

### 6. Entrega
**Punto de aprobación 2:** presentar al usuario:
- El copy final, listo para copiar.
- La pieza visual o su especificación, si aplica.
- Rutas de todos los archivos generados.
- Datos usados y su fuente.

Indicar que nada se ha publicado. Si el usuario aprueba, renombrar el copy final agregando `_aprobado` y registrar quién aprobó y la fecha al final del archivo.

## Reglas
- No saltar al guardián de marca aunque la pieza parezca correcta.
- No publicar ni programar nada: la publicación es manual.
- Si en cualquier paso falta un dato de marca, detenerse y preguntar.
