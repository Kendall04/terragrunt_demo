# Sentinel: retirada AWS pendiente de autorización

Separación del repositorio: 10 noviembre 2026. Inventario AWS de solo lectura:
**17:07 UTC**, cuenta `341936017254`, `us-east-1`, prefijo
`ecs-portable-r20261026p1`. Ningún recurso Sentinel se detuvo ni eliminó aquí.
La implementación recuperable se identifica en [el archivo de separación](history/SENTINEL-SEPARATION.md).

## Alcance físico y datos

| Recurso | Exclusividad y tratamiento propuesto |
| --- | --- |
| Seis Lambda: ingestion, worker, watchdog, cleanup, backup-observer, egress-probe-a | Exclusivas. Cinco reglas EventBridge habilitadas; worker tiene dos targets. Retirar primero los disparadores y el event-source mapping SQS de ingestion, luego esperar invocaciones en curso. |
| Bus EventBridge `ecs-portable-r20261026p1` y regla `ecs-portable-r20261026p1-reports` | Exclusivos; la regla del bus privado envía a reports SQS. Es distinta de las cinco reglas programadas del bus default. Conservar su configuración y deshabilitar el forwarding durante la pausa. |
| Tres SQS: reports, reports-dlq, operations-dlq | Exclusivas. A las 17:07 había **1.620** mensajes visibles en operations-dlq; las otras dos estaban vacías. No se recibieron ni purgaron mensajes. Retención SQS no es archivo permanente: decidir exportación antes de su vencimiento. |
| DynamoDB `ecs-portable-r20261026p1-state` | Journal exclusivo, aproximadamente **141 MB**, PITR habilitado de **un día**. Conservar revisiones, incidentes, efectos y las cuatro compensaciones. TTL/cleanup y PITR no sustituyen un archivo histórico. No eliminar la tabla ni desactivar su protección. |
| S3 `snt-ecs-portable-r20261026p1-341936017254-us-east-1` | Archivo exclusivo; conservar **todas las versiones**, manifiestos y permisos de lectura futuros. No vaciar. El CMK de archivo es compartido con backups SQL. |
| Bucket de access logs `snt-logs-*` del mismo despliegue | Logs exclusivos, con retención configurada. Conservar los necesarios antes de cualquier cambio de Lifecycle. Verificar el nombre físico en el state instalado. |
| SNS `ecs-portable-r20261026p1-notices`, suscripción y siete alarmas del mismo prefijo | Exclusivos. Retirar acciones/disparadores antes del topic. No reenviar notificaciones para probar. La clave de cifrado también autoriza alarmas ajenas a Sentinel. |
| Seis log groups `/aws/lambda/ecs-portable-r20261026p1-*` | Unos **21 MB** en total. Retención de 7 días (observers/probe) o 30 días (runtime). Preservar la selección histórica antes de que expire. |
| Roles/boundaries/policies, EventBridge permissions, SG y ENI de la probe | Retirar solo identidades/SG exclusivos, una vez detenidos consumidores y liberada la ENI Lambda. No eliminar VPC, subnets, rutas ni SG de ECS/SQL/NAT. |

**Conservar fuera de esta retirada:** bucket y productor SQL, su timer, sus
credenciales y policy `EcsDevSqlBackupV220261105`; CMK backup/archivo
`30f01bb6-03b5-4e5f-b7a8-e304fe607ced`; clave de texto/Secrets Manager;
CMK SNS `9d9a8e10-ffd6-4038-b7f0-c3f1ebb4c444` hasta separar sus usos por
alarmas NAT/E13 y DEV. No retirar una clave por el nombre del experimento.
La tabla usa la clave AWS-managed de DynamoDB (`KeyManager=AWS` verificado);
no es una CMK propia para retirar.

## Coste recurrente orientativo

Estimación, **no factura ni presupuesto nuevo**, sin descontar Free Tier:
aproximadamente 219.000 invocaciones programadas/mes; con 0,5 s por invocación
y hasta 512 MiB, Lambda sería ~USD 0,96/mes. Siete alarmas estándar serían
~USD 0,70/mes. Añadir DynamoDB requests/storage/PITR, S3 versiones/requests,
KMS, SQS, SNS y logs: **orden de USD 2–6/mes**, sensible a duración, reintentos
y crecimiento del journal. No es un tope. Las claves compartidas y sus cargos
no desaparecen al detener Sentinel. Los datos retenidos siguen teniendo coste.

Fuentes de precios: [Lambda](https://aws.amazon.com/lambda/pricing/),
[CloudWatch](https://aws.amazon.com/cloudwatch/pricing/),
[DynamoDB](https://aws.amazon.com/dynamodb/pricing/),
[KMS](https://aws.amazon.com/kms/pricing/), [S3](https://aws.amazon.com/s3/pricing/).
El hosting DEMO mantiene su presupuesto independiente de USD 1/mes.

## Procedimiento propuesto; no ejecutado

1. **Preservar:** exportar journal/compensaciones, configuración de schedules,
   mappings, policies, versiones de código y metadatos del archivo. Los recibos
   privados ya conservados siguen intactos. Resolver expresamente la conservación
   del contenido de DLQ y logs antes de su expiración; leer estadísticas no
   preserva mensajes. No recibir mensajes ni exportar datos sin el alcance aprobado.
2. **Recuperar el owner IaC exacto:** checkout aislado del commit de origen de
   `ci/authority/retired-sentinel.json`; usar `operations/integrations/portable/trial` y el state,
   inputs privados y versiones de paquetes de la instalación real. El root
   `terraform/infra/sentinel-backup` es una generación anterior, no el owner
   instalado. Comparar `state list`, recursos físicos y plan fresco. No importar
   ni adoptar recursos compartidos, no reutilizar un plan de noviembre anterior.
3. **Pausa reversible autorizada:** preparar un cambio en el owner existente
   para deshabilitar solo sus cinco reglas programadas, la regla reports del
   bus privado y el mapping de ingestion. Revisar
   el plan: cero borrados y cero cambios en SQL, NAT/E13, API, CD o CloudFront.
   No hay un interruptor IaC universal ya implementado: el cambio explícito en
   esos recursos requiere revisión y autorización. No usar E2 ni force unlock.
4. **Esperar y comprobar:** cero invocaciones en curso y cero nuevos efectos
   del runtime; conservar queues/journal/archive. No confundir permisos vencidos
   con desactivación. Eliminar luego las funciones/roles/alarms exclusivos solo
   mediante un plan acotado aprobado; respetar dependencias Lambda/ENI/SG.
5. **Retención separada:** tabla, buckets/versiones, DLQ, logs y claves requieren
   una decisión explícita. No ejecutar un `destroy` global que los incluya.
   Preparar su retención/importación en el futuro proyecto antes de retirar el
   owner; no basta con quitar un recurso del código y aplicar.
6. **Readback independiente:** API `/ready` 200, mismo digest/revisión ECS,
   NAT ASG/E13 intactos, backup horario reciente, claves compartidas habilitadas,
   CloudFront operativo. Registrar inventario residual y costes.

La siguiente autorización puede limitarse a **preservación y pausa reversible**.
Los borrados de datos/recursos y la retirada de claves no están autorizados.
