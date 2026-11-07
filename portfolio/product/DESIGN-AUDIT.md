# Revisión final de diseño — 7 noviembre 2026

Se aplicaron Impeccable (dirección, critique, craft floor y audit) y Vercel
web-design-guidelines en modo documental revisado. No se ejecutó el detector
descargable de Impeccable ni se atribuye a él esta medición. La instalación no
incluye engine, hooks ni automatización live. Pins en [DESIGN.md](DESIGN.md).

## Comparación verificable

| Vista | PR #36 | Rediseño |
| --- | --- | --- |
| Product Demo | [Antes](evidence/desktop-product.png) | [Después](evidence/redesign/desktop-product.png) |
| Sentinel | [Antes](evidence/desktop-explorer.png) | [Después](evidence/redesign/desktop-explorer.png) |
| Incidente NAT | [Antes](evidence/desktop-resilience-nat.png) | [Después](evidence/redesign/desktop-resilience-nat.png) |
| Recuperación SQL | [Antes](evidence/desktop-resilience-sql.png) | [Después](evidence/redesign/desktop-resilience-sql.png) |
| Móvil Product Demo | [Antes](evidence/mobile-demo.png) | [Después](evidence/redesign/390-demo.png) |
| Nueva portada | No existía | [1440 px](evidence/redesign/1440-overview.png), [320 px](evidence/redesign/320-overview.png) |

Primera impresión: la portada explica plataforma, relaciones y evidencia antes
del formulario. Una navegación sustituye las dos anteriores. Sentinel tiene una
sección propia; los resultados medidos tienen límites visibles. Product Demo
separa la tarea de escritura del recorrido explicativo; las listas recuperadas
ya no compiten con tres tarjetas repetidas. Las cronologías relacionan actores,
pasos y evidencia sin convertirlos en telemetría actual.

## Auditoría técnica y visual

Juicio manual usando la rúbrica Impeccable, no una certificación ni una evaluación
externa independiente:

| Dimensión | /4 | Evidencia y límites |
| --- | --- | --- |
| Accesibilidad | 3 | Semántica, etiquetas, foco, skip link, teclado, contraste; falta ensayo con lector de pantalla físico |
| Rendimiento | 4 | ESM nativo, cero dependencias de producción, fuente local precargada, diagramas bajo demanda |
| Tema | 3 | Tokens coherentes; colores semánticos especializados adicionales; solo tema oscuro intencional |
| Responsive | 3 | Cinco anchos sin overflow, controles táctiles; Chrome emulado, no dispositivo táctil físico |
| Integridad | 4 | Roles ASG/E13 y Sentinel separados, evidencia fechada, sin métricas ficticias ni fallback AWS |
| Total | **17/20** | Good según la rúbrica; límites de validación explícitos |

[Medición de shell](evidence/redesign/DESIGN-AUDIT.json): 25 combinaciones de
vista/viewport PASS. 18 pares de color medidos, contraste 6,98–16,97:1. Botones
visibles ≥44 px de alto, un h1 por vista, inputs etiquetados, foco CSS y reduced
motion. No es un análisis de cada píxel de los visores Archify aceptados.

[Chrome/Playwright](evidence/BROWSER-QA.json): 57 capturas, cero errores JS y
cero peticiones externas. 1440/1920, tablet 768, móviles 390/320. Inspección visual
real de portada, formulario, Sentinel, NAT, SQL, atlas y evidencia. Se verificaron
zoom/fit, alternativas de lectura y sandbox opaco de los doce diagramas.

Hallazgos corregidos durante iteraciones:

- `visuals.mjs`: el contorno de red privada incluía visualmente NAT/Sentinel;
  ahora delimita aplicación/datos y etiqueta redes públicas y señales indirectas.
- `style.css`: menú partido a 320 px y duración incómodamente fragmentada;
  corregidos mediante composición compacta y números sin corte.
- `style.css`: tres selectores de portada tenían 40 px; ampliados a 44 px.
- `app.mjs`: Escape cierra el menú y devuelve el foco al botón.

## Revisión Vercel y límites aceptados

Reglas consultadas nuevamente el 7-nov en
[web-interface-guidelines](https://github.com/vercel-labs/web-interface-guidelines/blob/main/command.md).

- `index.html`: landmarks, skip link, etiquetas, idioma y tema: PASS.
- `app.mjs`: controles nativos, navegación con anchors, foco y anuncios: PASS.
- `style.css`: foco, contraste, reduced motion y layouts: PASS medido en el shell.
- `app.mjs`, Product Demo: borrador y ejemplos viven solo en memoria; navegar o
  recargar puede perder texto sin guardar. No es un editor persistente. P2 conocido.
- `app.mjs`, reset DEMO: reinicio inmediato solicitado por el contrato existente;
  afecta solo datos sintéticos de esta pestaña, nunca registros AWS. No se añadió
  un modal de administración al flujo de prueba.
- Timestamps de incidentes están fijados como evidencia UTC, no localizados como
  si fueran eventos actuales. Español usa mayúsculas de frase, no Title Case inglés.
- Los gestos internos Archify no se reimplementaron. Zoom mediante botones,
  inspector, fuente y hoja textual siguen disponibles. No se afirma una auditoría
  universal WCAG de los HTML originales que esta tarea debía preservar.

No quedan fallos P0/P1 conocidos en el alcance observado. Las limitaciones de
dispositivo físico y lector de pantalla permanecen documentadas, sin inventar PASS.
