# Cloud Resilience Laboratory — dirección de producto

Rediseño de PR #36, base `21701c91026c0b6b4de7afff0175c529a2d0995e`.

## Público y propósito

Un reclutador técnico debe entender en un minuto qué construyó Kendall; un ingeniero
senior debe poder seguir la evidencia y sus límites. La portada presenta la
plataforma y su capacidad de recuperación. El visitante después elige experimentar
con texto sintético, recorrer un incidente histórico o investigar su arquitectura.

## Crítica del diseño anterior

- Doble navegación superior/lateral y contexto repetido ocupaban el primer plano.
- Tres tarjetas explicativas, formulario y recorrido tenían peso visual similar.
- Tamaño de cuerpo pequeño y bordes continuos obligaban a leer un panel administrativo.
- El formulario aparecía antes de explicar por qué la plataforma importa.
- La cronología narraba hechos, pero no mostraba relaciones entre recuperación y observación.
- Atlas correcto y aislado; su shell no ofrecía una jerarquía de exploración clara.

## Direcciones exploradas

1. Consola de operaciones: familiar, pero repite el problema del dashboard; descartada.
2. Ensayo editorial: buena lectura y grandes resultados, pero demasiado estático para
   explorar relaciones; retenemos espacio, ritmo y jerarquía, no su estructura completa.
3. Laboratorio de sistemas: una topología manipulable abre la experiencia; las líneas
   representan relaciones reales y las cronologías permiten leer un incidente.
   **Elegida** por conectar el diseño con la especialidad demostrada del proyecto.

## Decisiones visuales

- Superficies: tinta `#0b1017`, azul pizarra `#121c29`, texto `#eef2f7`, secundario
  `#aebdce`; ámbar `#ffb454` para acción/fallo, menta `#76ddc1` para confirmación,
  lavanda `#b6a7f2` para observación Sentinel. Color nunca sustituye una etiqueta.
- Sora autoalojada, pesos 400/600, SIL OFL. Escala fluida 16–80 px; monospace solo
  para tiempos/IDs/código. Texto de lectura limitado en ancho, encabezados balanceados.
- Una navegación superior de cinco destinos. Overview presenta; Product Demo opera;
  Architecture explora; Resilience relata; Evidence verifica.
- Firma: rutas de datos/control/observación dibujadas con SVG geométrico accesible,
  sin ilustraciones ficticias, números decorativos ni paneles iguales repetidos.
- Movimiento responde al visitante; no loops automáticos, no falsa telemetría.
  Reduced motion conserva los cambios de estado sin desplazamiento animado.
- El visor Archify conserva bytes y pins originales; el rediseño pertenece al shell.

## Metodología y procedencia

Impeccable 4.8.0, revisión `687bc381bc9091bf252c0a05303640561014a425`,
usado en modo documental: dirección, craft floor, critique y audit. Instalación
local limitada a Markdown; no scripts, engine, hooks, agents ni live. Las rutinas
de entrevista/CLI no se ejecutan: el brief ya decide público, autonomía y límites.
Vercel web-design-guidelines revisión `1a2c79d4e6c4a2283dc2c614b6538cbe1ed5ca62`
para auditoría de interfaz; sus reglas remotas se releen al cierre.
Anthropic frontend-design se evaluó y no se instaló por redundancia.

La revisión final distingue juicio visual, pruebas automatizadas y limitaciones;
no atribuye a un detector Impeccable ninguna ejecución que no se haya realizado.

## ECS independiente de Sentinel — 10 noviembre 2026

Se conserva esta dirección visual. La superficie antes dedicada a Sentinel
explica ahora CI → ECR → ECS. El hero representa backups SQL; ASG/E13 conserva
la recuperación NAT. Cinco vistas actuales tienen prioridad y doce snapshots
permanecen en Historia, con sus lecturas originales. No se rediseña el sitio.
