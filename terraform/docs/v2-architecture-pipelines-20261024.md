# ECS V2: arquitectura y pipelines recomendados — 2026-10-24

Revisión local sobre `276dfd85674b99c1ef64c0bf7c622a50b94abf71`. Diseño propuesto, no cambio operativo ni autorización de despliegue. Actualiza las recomendaciones del 16 de octubre con az6/b1/b2 y las decisiones posteriores del propietario. La configuración de modelo solicitada fue Astra Medium; esta revisión no dispone de una comprobación del modelo efectivo.

## Decisión recomendada

Conservar una API sencilla, dos AZ y **una SQL Express activa en EC2**. Operar el runtime por sesiones de demostración, con una tarea Fargate normalmente; habilitar dos tareas distribuidas sólo para demostrar disponibilidad de aplicación. El color inactivo permanece en cero salvo durante despliegue. Ante pérdida de SQL, crear el sustituto desde cero en una AZ explícita, igual o distinta, y restaurar un backup válido. No mantener otra DB, añadir PKI, ampliar negocio ni montar PROD permanente para completar el CV.

Esto demuestra ingeniería de entrega, durabilidad, recuperación y observabilidad sin vender alta disponibilidad de base de datos. La segunda AZ y dos servicios blue/green no convierten una única tarea o SQL única en alta disponibilidad. Conservar inicialmente API Gateway/VPC Link/ALB y la red existente: eliminarlos ahora exigiría otra migración y desviaría el cierre. No ampliar el mecanismo de recuperación NAT dentro de Sentinel/backups.

## Evidencia y límites

| Hito | Qué acredita | Qué sigue sin acreditar |
| --- | --- | --- |
| V1, entrega A→B→A | Imágenes distintas por digest, continuidad SQL/KMS y rollback de aplicación | Rollback de migraciones, PROD, despliegue Fargate actual de .NET10 |
| az6 | Backup/restore entre AZ, CHECKDB, descifrado y lectura/escritura API; 142.630783 s con destino preparado y dos reparaciones | Recuperación desde cero con artefacto inalterado, RPO general, continuidad ECS completa |
| b1 | Ingesta sintética, persistencia y dos avisos SNS recibidos por el usuario | Observador periódico real; drenaje total de outbox: quedaron efectos no soportados |
| b2 | Creación/retirada TF/TG de 43 recursos, paquete inerte, Lambda/cursor vacíos | SSM terminó AccessDenied/−1 dos veces: cero eventos y cero avisos; productor no activado |
| Código local | Observador/publicador, integración Sentinel, empaquetado y pruebas específicas | Servicio permanente, CI remota de fuentes privadas y ensayo integrado de extremo a extremo |

Fuentes: [entrega, sección A→B→A](deployment.md#real-sourcetransport-qualification-and-distinct-digest-dev-rollback), [az6, líneas 964 y 1030 en la base revisada](../../operations/sql-backup/recovery/RUNBOOK.md), [b1](../../operations/integrations/NATIVE-TRIAL-2026-10-23.md), [b2 y diagnóstico SSM](../../operations/integrations/NATIVE-TRIAL-2026-10-24.md). Son recibos históricos, no inventario vivo. Todos esos ciclos están cerrados; sus presupuestos no financian otro ensayo.

## Arquitectura y propiedad

El tráfico actual recorre API Gateway HTTP → VPC Link → ALB interno → Fargate → SQL privada. KMS protege los textos de aplicación; su clave es distinta de la protección de backups. `/health` acredita vida del proceso, no disponibilidad SQL/KMS; `/ready` y las pruebas de negocio deben preceder a la promoción. La topología y propietarios están en [architecture.md](architecture.md).

| Componente | Propietario recomendado | Regla |
| --- | --- | --- |
| Red, grupos, SQL, esqueletos ECS | Terraform/Terragrunt mediante lifecycle existente | No competir con runtime sobre revisiones, réplicas ni forwarding |
| Imagen, revisión de tarea, tráfico blue/green | Entrega WP3/WP4 existente | Digest cualificado, readiness y arbitraje E2; no sustituir por CLI libre |
| Estados DEV ordinarios | E16 | Un escritor; no activar WP5 contra sus mismas claves |
| Sentinel: Lambdas, código/configuración, colas, tabla, archivo, SNS y horario | Root TF/TG Sentinel dedicado | Un propietario por recurso, sin CloudFormation ni actualizador CLI paralelo en ruta final |
| Backup/observador/publicador | Unidades existentes en el host SQL final | Credenciales por rol; productor sólo envía al contrato/cola autorizados |
| Backups, claves y estado terminal | Ciclo duradero separado | No incluir en teardown de runtime por defecto |

El host dedicado de b2 fue un instrumento de prueba, no un nuevo microservicio ni requisito permanente. Recomiendo instalar finalmente las unidades existentes en el SQL activo y conservar Sentinel fuera de ese host: así la falta de señales del host puede ser observable. Una comprobación emitida exclusivamente por el propio host no demuestra detección de su desaparición. El watchdog externo debe cualificarse con su política real antes de anunciar esa capacidad.

La implementación [sentinel-backup](../infra/sentinel-backup/README.md) sigue siendo un sandbox de hasta 24 h. Para operación permanente hay que revisar cadencia, TTL, retención, dedupe y permisos; quitar una fecha de expiración no constituye esa revisión. CloudFormation fue el piloto b1 histórico; no importar sus recursos ya retirados. El diagrama final integrado de demo sigue aplazado hasta E2E; esta revisión no modifica los cinco Archify.

## Recuperación SQL bajo demanda

Implementar un único procedimiento parametrizado, sin dos variantes de código por AZ. Entradas cerradas: identidad de entorno/estado, generación del origen, modo SAME_AZ/CROSS_AZ, AZ ID objetivo explícito, AMI/paquete/digest, manifiesto S3 y VersionId, política de antigüedad y presupuesto. Resolver SAME_AZ desde evidencia del origen; CROSS_AZ exige un ID distinto. Rechazar defaults ambiguos y backups incompatibles. No seleccionar silenciosamente la primera subnet como en [ordinary-main.tf](../modules/target/dev/data/ordinary-main.tf).

1. Iniciar el reloj **antes de crear** el sustituto; registrar último write testigo confirmado y manifiesto durable seleccionado. Validar cadena, hashes, versiones, permisos S3/KMS y compatibilidad SQL sin exponer secretos.
2. **Fencing obligatorio**: impedir nuevas escrituras del origen y de clientes con conexiones antiguas. Verificar el resultado del mecanismo elegido y su generación; una orden aceptada, ausencia SSM o caída de AZ no prueban aislamiento. Si no puede demostrarse, no habilitar escrituras en el reemplazo. Diseñar la operación exacta y permisos antes del próximo ensayo.
3. Crear host/disco cifrado en la AZ elegida desde artefacto inmutable; instalar SQL y restaurar con rutas controladas. Mantener migraciones automáticas deshabilitadas durante recuperación; ejecutar CHECKDB y verificar esquema, testigos e identidad.
4. Cambiar la referencia de conexión fuera del estado Terraform, renovar tareas/conexiones y comprobar readiness SQL/KMS y lectura/escritura/descifrado de la API desplegada. Promover tráfico sólo después. No limitar la aceptación a una API loopback del host.
5. Registrar RTO total y segmentos de provisión, instalación, descarga, restore, validación y corte. Medir RPO con el write testigo respecto del backup efectivamente recuperado, explicitando resolución de la medida. Retirar sustitutos fallidos y dejar exactamente una SQL activa, conservando evidencia y backup acordados.

Recomiendo mantener inicialmente el disco del host como reemplazable, sin introducir un volumen persistente como sustituto de backups. El código actual cifra el root y lo borra al terminar la instancia. Por ello el teardown necesita un backup validado y una disposición explícita de datos; un volumen por AZ tampoco resuelve recuperación entre AZ. Si se separa después el volumen de datos, deberá tener propietario/retirada propios.

Mantener la retención existente **2+2 días**. La cadencia horaria y umbral de dos horas documentados son parámetros de laboratorio, no un SLO demostrado. Las 168 h de b2 sólo admitían un manifiesto histórico: no trasladarlas a salud normal. No prometer RPO de una hora ni RTO de 60 minutos hasta medir esta ruta completa, incluido fallo de backup y recuperación desde cero.

## Pipelines: simplificar entradas, conservar controles

Hay 27 archivos de workflow en la base. No son 27 pipelines operativos: varios son reutilizables o entradas inactivas deliberadas. Recomiendo cinco entradas visibles: CI, Release, Deploy DEV, Rollback DEV e Infra lifecycle. Sentinel utiliza el lifecycle de su root separado; no necesita un segundo sistema de despliegue. PROD queda inactivo hasta justificar aislamiento y coste.

| Entrada | Contrato recomendado | Evidencia/gap actual |
| --- | --- | --- |
| CI por PR/push | Sin OIDC; scope conservador; build/test, higiene y seguridad estática; resultado requerido único | `ci.yml` ya selecciona y verifica jobs; conservar `CI Validation` y probar selección fallida/paths nuevos |
| Release manual | Construir una vez, cualificar, publicar digest y manifiesto/procedencia | `release-build.yml` delega al controlador inmutable; no rebuild en deploy |
| Deploy DEV manual | Release ID válido, exclusión E2, readiness de tareas candidatas, mover tráfico, recibo | `deploy-dev.yml`; grupos de concurrency distintos no serializan deploy y rollback entre sí |
| Rollback DEV manual | Seleccionar release histórico compatible, verificar y promover | `rollback-manifest.yml`; es rollback de imagen, nunca reparación automática de esquema/datos |
| Infra lifecycle manual | Plan guardado/identificado → apply del mismo plan; DOWN con evidencia y preservaciones | Conservar E16 y estados separados; plan de recuperación nuevo requiere contrato específico |

Referencias directas: [ci.yml](../../.github/workflows/ci.yml), [ci-dotnet.yml](../../.github/workflows/ci-dotnet.yml), [ci-repo-hygiene.yml](../../.github/workflows/ci-repo-hygiene.yml), [ci-terragrunt.yml](../../.github/workflows/ci-terragrunt.yml), [release](../../.github/workflows/release-build.yml), [deploy](../../.github/workflows/deploy-dev.yml), [rollback](../../.github/workflows/rollback-manifest.yml), [reusable release](../../.github/workflows/e1-release.yml), [generador de requests](../../scripts/workflow_requests/render.py), [operación E16](portfolio-operations.md).

Release/Deploy siguen fijados a `Kendall04/terragrunt_demo`, rama `codex/final-github-actions-cicd` y reusable `f0ba8ad1d6528d362693c8de932f935c8084529d`. La revisión de ramas no debe sustituir ese pin por `main`. El diseño destino es PR hacia main en el repositorio final, pero mover repositorio/ref exige generar, revisar y publicar un nuevo controlador inmutable y alinear trust, environments y configuración del gateway. No modificar únicamente el YAML para aparentar habilitación.

OIDC actual restringe environment, audiencia y subject con `job_workflow_ref`; el request role solicita operaciones al gateway, no administra directamente ECS/ECR/estado. Conservar esta separación, acciones externas por SHA y `persist-credentials:false`. Leer los claims localmente no reemplaza su validación por AWS. En la futura migración comprobar el subject efectivo: GitHub documenta formatos inmutables nuevos con IDs para repositorios nuevos; no copiar el trust antiguo sin cotejo. [Guía oficial OIDC AWS](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws).

Antes de retirar entradas legacy/inactivas, actualizar su generador, tests de contratos, scope selector y documentación; cotejar required checks y environments remotos. No cambiar protecciones desde esta revisión. Cancelar CI obsoleta es razonable; deploy/rollback/teardown deben reconciliar resultados inciertos y conservar la exclusión durable, no cancelarse a mitad para ahorrar tiempo.

## Reproducibilidad, seguridad y pruebas faltantes

- `ci-dotnet.yml` restaura sin `--locked-mode`; introducir lock de dependencias y restauración bloqueada en un cambio dedicado, probar caché vacía/reutilizada y ligar SBOM/procedencia al digest cualificado. No declarar que las pruebas actuales incluyen ese control.
- Mantener análisis IaC existente y resolver sus hallazgos por severidad/alcance. No rebajar el gate para que quede verde. La revisión de [E14-B](e14b-toolchain-reproducibility.md) sigue sin el recibo original necesario para normalizar cinco diferencias h1; copiar hashes no corrige el generador.
- Mantener AWS5.100 en roots originales y AWS6.27 en el root Sentinel aislado mientras se cualifica una migración deliberada. Su [schema y firma](../infra/sentinel-backup/provider-qualification.json) acreditan dotnet10 local; no inferir compatibilidad por el número de .NET. Calificar Linux y fuente privada Sentinel reproducible para CI, sin tokens en artefactos.
- Tratar SQL `TrustServerCertificate=True`, ALB HTTP interno, migraciones al arrancar con permisos amplios y acceso público sencillo como límites explícitos del laboratorio. No introducir PKI de microservicios para corregirlos: no hay llamadas de negocio HTTP internas entre dos servicios. Priorizar principal de runtime SQL separado del migrador y compatibilidad de esquema para blue/green en un cambio posterior.
- Sentinel: probar duplicados/reintentos/UNKNOWN/recuperación y estados terminales reales de outbox. Efectos de probes no soportados deben seguir visibles o recibir una clasificación explícita sin ejecución; nunca marcar ejecutado para declarar drenaje. Ningún evento backup debe ejecutar ni encolar reparación NAT. ACK sólo según persistencia/aceptación del contrato; Publish aceptado no es entrega inbox.
- SSM b2 tiene fallo de autorización previo a ejecución, **causa exacta no demostrada**. El suplemento probado no lo resolvió. La siguiente propuesta debe aportar trazas permitidas que identifiquen la evaluación denegada antes de otro cambio IAM. Una secuencia de arranque inmutable puede simplificar futuros ensayos, pero es un diseño nuevo revisable, no una ruta para repetir el comando denegado.

## Coste y retirada desde el diseño

Recomiendo sesiones de runtime bajo demanda y demo estática con etiquetas históricas entre sesiones. Dos AZ son suficientes para el objetivo; una tercera y una segunda SQL permanente no añaden evidencia proporcional. Dos tareas sólo durante la prueba de distribución/fallo; [ECS AZ rebalancing](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service-rebalancing.html) no hace redundante una única tarea.

Presupuestar por ciclo: horas de Fargate + SQL EC2/EBS + ALB/VPC Link según consumo facturable + NAT instances/IPs + transferencia + logs + almacenamiento/requests backup/KMS + Sentinel. Separar coste retenido de S3/versiones/KMS/estado del runtime retirado. No hay estimación nueva en dólares ni factura consultada en esta revisión. Calcular el importe concreto con tamaños, región y tarifas vigentes antes del siguiente consentimiento; no reutilizar los USD1/USD2 cerrados.

Evaluar gateway endpoints S3/DynamoDB cuando eviten tránsito NAT sin otra complejidad: [AWS no cobra adicional por esos endpoints](https://docs.aws.amazon.com/vpc/latest/privatelink/gateway-endpoints.html). No solucionan por sí solos todo el egress (ECR, logs, SSM y otros servicios); comparar endpoints de interfaz cobrados contra la red existente antes de cambiarla.

Cada ciclo debe incluir inventario planificado más recursos implícitos, callbacks completos del provider create/read/update/delete, nombres/identidades, límites efectivos de permisos y reversión. Registrar IDs al crear. Retirada: parar productor/entradas/horarios, exportar evidencia, reconciliar efectos y apagar consumidores; quitar protecciones sólo del ensayo; borrar runtime y datos sintéticos según plan; vaciar versiones de buckets propios cuando proceda; retirar IAM temporal al final y cotejar originales. Reservar margen práctico dentro del techo aprobado, sin nuevos cortes de minutos dependientes de una reacción. Una simulación IAM no garantiza callbacks AWS ni autoriza ampliar permisos tras un rechazo.

## Secuencia de implementación propuesta

| Cambio posterior | Archivos/contratos | Gate de aceptación |
| --- | --- | --- |
| 1. CI reproducible y menú reducido | `.github/workflows/ci*.yml`, selector, `scripts/workflow_requests/render.py`, tests asociados | Locks auténticos; selección conservadora; required checks preservados; fuentes Sentinel fijadas |
| 2. Recuperación desde cero | `operations/sql-backup/recovery/`, root de recuperación y contrato de entrega existentes | SAME/CROSS AZ, fencing negativo, backup inválido, interrupción/reanudación, reloj completo y retorno API |
| 3. Observabilidad integrada | `observer.py`, `sentinel_publish.py`, units, root `sentinel-backup` | Productor periódico real, ausencia/antigüedad/fallo/UNKNOWN/recuperación, dedupe y outbox honesto, sin NAT |
| 4. Migración de entrega final | Generador E1, pins, OIDC/env/gateway y README | Un repositorio/propietario por recurso, main/PR coherentes, ensayo release→deploy→rollback y DOWN |
| 5. Evidencia pública final | Portfolio y Archify existentes | Sólo después del E2E, separar actual/histórico/propuesto; no añadir negocio |

No ejecutar otra infraestructura mientras una corrección necesaria puede demostrarse localmente. Para la prueba real, agrupar plan/budget/permisos/retirada completos y correo si procede; fallos recuperables se diagnostican dentro de ese alcance sin recrear ciclos por rutina.

## Autoridad y validación de esta revisión

Esta entrega cambia sólo documentación. No ejecuta builds, Terraform init/plan, AWS, workflows remotos, publicación ni migración. Se comprobaron rutas enlazadas y diff documental. Los resultados de tests mencionados en recibos siguen siendo históricos; no se relabelan como corridos hoy.

Los cambios de fuente propuestos requieren el siguiente encargo de implementación. Publicar workflows/nuevo repositorio y modificar OIDC, environments/IAM, datos, infraestructura o gasto requieren su alcance concreto antes de ejecutar. La configuración actual remota de GitHub, claims, protecciones y coste real no se cotejó; los YAML y recibos locales sí. PKI está fuera de ECS, y el diagrama final de observabilidad permanece aplazado por decisión del propietario.
