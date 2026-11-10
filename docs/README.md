# Documentación de ingeniería

[Proyecto](../README.md) · [DEMO pública](https://d20ioz705caon7.cloudfront.net/) · [Atlas actual](interactive/CURRENT-INDEX.md)

| Tema | Referencia vigente |
| --- | --- |
| Topología y ownership | [Arquitectura](../terraform/docs/architecture.md) |
| CI/CD automático DEV y rollback | [Delivery simplificado](DEV-DELIVERY-DESIGN.md) |
| API / SQL / confianza TLS | [Arquitectura de datos](../terraform/docs/architecture.md#current-contract--application-and-data) · [TLS por ambiente](../demo-api/deploy/sql-trust/README.md) |
| Backup horario y recuperación | [SQL](../operations/sql-backup/README.md) · [recuperación nativa](../operations/sql-backup/recovery/NATIVE-RECOVERY.md) · [retención y holds](../operations/sql-backup/storage/README.md) |
| Operación y retirada | [Ciclo nativo DEV](../terraform/docs/native-dev-lifecycle.md) |
| Seguridad y límites | [Estrategia de secretos](../terraform/docs/secrets-strategy.md) · [revisión técnica fechada](ENGINEERING-REVIEW.md) |
| Validación y efectos | [Guía de validación](../terraform/docs/validation.md) |
| DEMO, AWS Edition local y hosting | [Frontend](../portfolio/product/README.md) · [CloudFront](../portfolio/product/HOSTING.md) |

DEV tiene entrega automática demostrada. PROD no está activado ni validado.
El runtime es un laboratorio con costes y retirada supervisada; el sitio estático
permanece independiente.

## Evidencia fechada

- [ECS V2 en AWS](DEV-V2-20261105.md).
- [SQL SAME-AZ/CROSS-AZ y seguridad](V2-RECOVERY-SECURITY-20261105.md).
- [Primer CD DEV automático](https://github.com/Kendall04/terragrunt_demo/actions/runs/42751096835).
- [TLS definitivo CA-only entregado por CD](https://github.com/Kendall04/terragrunt_demo/actions/runs/42761946295/attempts/2).
- [Auditoría CI/CD previa](CI-CD-REVIEW.md): conserva el diagnóstico de su fecha,
  no sustituye el diseño simplificado y la evidencia de ejecución posteriores.

## Historia y proyecto independiente

Reliability Sentinel ya no es una dependencia de ECS.
[Código y procedencia recuperables](history/SENTINEL-SEPARATION.md),
[retirada AWS pendiente](SENTINEL-RETIREMENT.md) y
[ensayos originales](SENTINEL-CHAOS-20261106.md) conservan el trabajo.
El [atlas del 6 noviembre](interactive/V2-INDEX.md) y V1 son snapshots históricos.
No atribuir a la instalación actual la observación/notificación de Sentinel.
