# ECS V2: atlas actual

Snapshot técnico de **10 noviembre 2026**. DEV automático demostrado; PROD no
instalado ni validado. Sentinel continúa por separado: su runtime fue retirado. Sus diagramas y
archivos históricos no son dependencias operativas de ECS.

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
node scripts/diagrams/readable.mjs --current
node scripts/diagrams/readable.mjs --current --check
node --test scripts/diagrams/test-diagrams.mjs
node --test portfolio/product/test-product.mjs
node portfolio/product/server.mjs
```

Abrir `http://127.0.0.1:4182/architecture`. Repetir para los cinco IDs de la tabla.
`validate`, `deliver`, `check` y `browser-check` deben pasar. La inspección visual
de escritorio/móvil es adicional. Las hojas textuales son derivados propios,
identificados como tales; no se atribuyen a la salida oficial de Archify.

## Revisión técnica y visual final

Revisión fijada a `33a32d44351810ab9a815af1da2d1f32d4b968ad`.

| Vista | Mejora principal |
| --- | --- |
| Plataforma | Target groups blue/green explícitos, color activo intercambiable y planos privados diferenciados. |
| CD DEV | Ocho etapas numeradas; build separado de ECR, salud antes/después del ALB, drenaje y registro S3/GitHub. Ownership Terraform en la lectura. |
| Red | Una fila por AZ; ECS elegible en ambas subnets, SQL en B. E13 independiente, EIP/ruta/SDC sin prometer failover entre zonas. |
| SQL | Diez pasos ordenados: copia final, entrada preservada, fence, nueva EC2, restore/CHECKDB y vuelta de la API. RTO fechados fuera de la ruta. |
| Identidades | Fronteras de acceso privado, ejecución ECS y administración/backups; API Gateway fuera de la VPC. CA DEV definitiva e identidades separadas. |

[Reproducción oficial](evidence/current/REPRODUCTION.json): cinco HTML idénticos
byte por byte y gates `validate`, `deliver`, `check`, `browser-check` PASS.
[Chrome](evidence/current/BROWSER-QA.json): 88 capturas privadas, cinco vistas
actuales en 320/390/768/1440/1920, doce históricas en escritorio/móvil, zoom,
pan, ajuste y cinco lecturas móviles. [Auditoría de interfaz](evidence/current/DESIGN-AUDIT.json):
foco, reduced motion, contraste de la paleta y ausencia de overflow; no es una
certificación WCAG. Revisión documental con Impeccable y Web Interface Guidelines.

Comparación representativa de la entrega:
[antes](evidence/current/before-1440-ecs-delivery.png) ·
[después](evidence/current/1440-ecs-delivery.png).
Red: [antes](evidence/current/before-1440-ecs-network.png) ·
[después](evidence/current/1440-ecs-network.png).
[Lectura móvil](evidence/current/mobile-reading-ecs-trust.png).
El repositorio conserva solo una selección de las capturas; hashes y tamaños
revisados quedan registrados. En móvil, la vista completa orienta y el detalle
se consulta ampliando o mediante la lectura textual.

Esta revisión solo consulta código/evidencia existente y publica contenido
estático. No consulta ni modifica el runtime AWS. El [readback anterior](evidence/current/ECS-READBACK.json)
conserva su fecha y alcance originales; no es una nueva validación de salud.
