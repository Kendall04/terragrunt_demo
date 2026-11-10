# ECS V2: atlas actual

Snapshot técnico de **10 noviembre 2026**. DEV automático demostrado; PROD no
instalado ni validado. Sentinel continúa por separado: sus recursos AWS pendientes
de retiro no se presentan como capacidad operativa de ECS.

| Vista | Qué explica | Fuente editable |
| --- | --- | --- |
| [Plataforma](ecs-platform.html) | API privada, KMS, SQL y backups | [JSON](source/ecs-platform.json) |
| [CD DEV y ownership](ecs-delivery.html) | Merge → CI → ECR → ECS blue/green → salud → release; Terraform separado | [JSON](source/ecs-delivery.json) |
| [Red / NAT E13](ecs-network.html) | AZ, egreso y recuperación NAT independiente | [JSON](source/ecs-network.json) |
| [Backups / recuperación SQL](ecs-sql-recovery.html) | Copias, aislamiento, restore y validación supervisada | [JSON](source/ecs-sql-recovery.json) |
| [Identidades / TLS](ecs-trust.html) | Roles, confianza DEV definitiva y límites de seguridad | [JSON](source/ecs-trust.json) |

[Abrir el Explorer público](https://d20ioz705caon7.cloudfront.net/architecture).
Incluye zoom, pan, ajuste de vista, fuentes verificables, alternativa textual y
hojas de lectura responsive. Los doce originales siguen en **Historia**.
[El atlas del 6 noviembre](V2-INDEX.md) conserva Sentinel y el CD entonces inhibido;
es evidencia histórica, no la arquitectura actual.

## Procedencia y regeneración

[GENERATION-CURRENT.json](GENERATION-CURRENT.json) fija fuentes, HTML, lecturas y
resultados. Archify **3.1.0**, commit
`1c2b42d660e4a7571813fb43839c79e3e9ca7720`, ZIP SHA-256
`ffedc53390c9da6e859f41e432c5d2d0615a23cf00a503181f07efbba88a7ce8`.
Se verificaron tanto el ZIP oficial como cada archivo extraído antes de ejecutarlo.
Usar Node **24.22.1** (runtime ya cualificado); no cambiar el generador para adaptar
un hash esperado. Los doce originales, sus pins y licencias permanecen intactos.

```sh
node <archify-autenticado>/bin/archify.mjs finalize architecture \
  docs/interactive/source/ecs-delivery.json docs/interactive/ecs-delivery.html \
  --repo-root . --quality showcase --out-dir <evidencia-nueva> --json
node --test scripts/diagrams/test-diagrams.mjs
node --test portfolio/product/test-product.mjs
node portfolio/product/server.mjs
```

Abrir `http://127.0.0.1:4182/architecture`. Repetir para los cinco IDs de la tabla.
`validate`, `deliver`, `check` y `browser-check` deben pasar. La inspección visual
de escritorio/móvil es adicional. Las hojas textuales son derivados propios,
identificados como tales; no se atribuyen a la salida oficial de Archify.

## Comprobación visual y operación

[Capturas verificadas](evidence/current/BROWSER-QA.json) registran Chrome local,
17 vistas aisladas y tamaños 320/390/768/1440/1920. Se inspeccionaron las cinco
vistas actuales; un recorte inicial de plataforma se corrigió en su JSON y se
regeneró oficialmente. Las lecturas textuales permiten explorar nodos en móvil.
[Readback AWS](evidence/current/ECS-READBACK.json): misma revisión/digest,
SQL/KMS saludables y publicación horaria posterior. No se ejecutó un nuevo
ensayo destructivo ni un despliegue API por esta separación.
