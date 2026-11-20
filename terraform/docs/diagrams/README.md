# Diagramas raster históricos

`architecture.png` y `cd-pipelines.png` son originales importados en el commit
`9aa2f0f` (27 de enero). Se conservan como historia, sin atribuirles procedencia
Archify ni afirmar que representan AWS DEV actual.

El primero simplifica incorrectamente una route table como salto del flujo HTTP;
el segundo muestra un modelo anterior al CD automático DEV y al ciclo nativo
actual. Sus omisiones de backups y recuperación fría no deben completarse
mentalmente como si ya figuraran en la imagen. Sentinel ya no es una dependencia.

Para ECS V2 use [las cinco vistas actuales](../../../docs/interactive/CURRENT-INDEX.md),
con fuentes editables, referencias al código, inventario AWS, auditoría y capturas.
