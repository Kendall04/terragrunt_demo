# ECS V2: arquitectura y pipelines recomendados — 2026-10-24

## Caller/registry closure - 2026-10-25

The earlier31/32 checkpoint below is superseded for caller consistency. With an
empty WP6 approval registry the existing generator must emit **no executable
reusable pin** for release/deploy/rollback. Five local caller files were regenerated
from that exact unchanged registry: release-build, deploy-dev, rollback-manifest,
cd-demo-api and cd. Seven historicalf0ba8ad1 reusable references were removed.
The affected jobs now have empty permissions, no OIDC/dispatch, and only an error
message followed by exit1. Branch/environment guards, dependencies and triggers
are preserved. No replacement pin, approval, installation or remote change exists.
The historical approved trial/pin remains preserved in Git and receipts.

Validation: **32/32 reproducibility PASS**, exact workflow render PASS and
**36/36 foundation PASS**, zero admission discrepancies. The new current-caller
regression proves the checked-in inactive jobs contain neither token acquisition
nor reusable dispatch. Existing synthetic positive authorization cases remain
separate from real approvals. No remote Actions job, AWS call, SSM or push ran.

The expanded WP6 suite is **61/62**, not global PASS. Its existing historical-ref
test fails while reconstructing an old whole-authority snapshot: the helper expects
obsolete WP5 selected digests. Its helper bytes, authority bytes and failing test
body match the pre-change base78df33e exactly, demonstrating an independent retained
fixture mismatch. That assertion was not weakened, skipped or changed; the failing
report remains. Correcting that shared historical projection is a separate narrow
local task, not grounds to fill approvals or select a guessed current pin.

Task-3/caller-registry-closure/qualification.json includes exact hashes, original
reference inventory and unchanged-input proof; SHA256:`2fd595147579c4503caa76e48133f2471f4798e3b76dfbb5d6cb5e0206258cde`.
This local consistency closure requires no additional access. Actual activation
still requires fresh genuine G1-G9/installed-source/endpoint observations and the
existing independently authorized approval mechanism. No such record was produced.


## Bounded security/pipeline closure update - 2026-10-25

This is a source-only follow-up to the historical design below. No Actions
workflow, GitHub setting, IAM, AWS resource, provider version or lock was changed.
No dependency/tool installation, download, image build or remote run occurred.

| Area | Current local disposition | Remaining acceptance |
| --- | --- | --- |
| SQL CLI recipe | Exact5110f5c fix retained in both bootstraps; AWS CLI uses `--no-install-recommends`; source pin reconciled | Resolved APT Depends/Recommends/installed versions on a newly admitted host; no installed-graphics/CVE verdict |
| SQL/base/ODBC recommendations | Existing explicit SQL/ODBC packages retained; no purge or unrelated option change | Native dependency graph and SQL/API checks before altering other packages |
| NuGet/image inputs | Four solution locks, CI/Docker locked restore and publish without restore already implemented; digest/non-root/API image qualification retained | Current vulnerability/SBOM assessment and deployed digest/runtime are not established by a pin |
| Provider checks | Official signed5.100 Windows ZIP/content h1 authenticated; CI recognizes only the exact Sentinel6.27 lock and one verified DEV platform delta | Sentinel's existing Windows/schema proof is not a fresh Linux provider qualification |
| Secrets/KMS/logging | Existing instance-only secret access, no shell tracing, separate backup/text keys and metadata-only configuration preserved | Effective IAM/boundaries/key policies and host logs require scoped native observation; values were not read |
| SQL runtime privilege/TLS | db_owner/startup migrations and `-C`/TrustServerCertificate remain explicit lab limits; recovery migration-off contract is locally qualified | Separate runtime/migrator privilege and SQL TLS validation need a dedicated tested change; PKI between services stays outside ECS |
| Publish versus deploy | Immutable release request, protected owner, task/route arbitration and empty approval registry retained | Local callers still reference historicalf0ba8ad1 while approvals are empty; do not claim those entrypoints currently admitted |

A concrete CI source-test mismatch was reproduced: the old root list rejected the
already reviewed separate Sentinel root; raw DEV/PROD equality rejected the one
additional Windows h1. The test now accepts **only** exact hash-pinned Sentinel
lock bytes, and only the exact additional h1 in DEV global/data/platform/apps/edge
when the independently authenticated origin receipt matches its reviewed hash.
After removing that one proven line for comparison, every remaining AWS block byte
must equal PROD. Unexpected hashes, versions, constraints, receipt drift, another
layer, deleted platform hash or modified Sentinel lock still fail. No actual lock,
provider selection, generator, runtime package or approval changed.

Focused full reproducibility suite: **32 executed,31 passed,1 retained failure,
zero errors/skips**. The failure is
`test_all_active_actions_recorded_or_explicitly_deferred`: delivery callers still
name the historical reusable pin, absent from the intentionally empty WP6 registry.
It is preserved as a real admission gate. This follow-up does not change Actions;
local synchronization to inactive generated callers or a newly reviewed immutable
installation is a subsequent delivery change, not permission to restore old grants.
No green whole-CI claim, historical-debt suppression or auto-approved record follows.

Evidence: task-3/pipeline-security-closure/{before.log,
reproducibility-owned-temp.log,qualification.json}. The initial sandbox run had
Windows private-temp cleanup errors; a new owned temporary directory resolved the
environmental issue. The retained failure above remains independently visible.
The36 foundation and236 WP1 cases from the prior closure were not repeated: only
the changed reproduction contract suite ran. Source inventory is refreshed only
for that reviewed test file and remains UNVERIFIED, never execution authority.

For tomorrow: the lock/source mismatch is closed locally; the remaining delivery
registry/caller discrepancy must remain blocked until its separate source/workflow
change. The live acceptance gate is still one admitted integrated AWS trial after
SSM execution admission is resolved and actual identities/resources reconciled.
That trial must prove cold SQL/CLI installation, backup and private restore,
version-bound Fargate/public API validation, periodic Sentinel observation and
retirement. No previous budget or historical receipt authorizes it.


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

## Adenda: superficie de seguridad y paquetes SQL

Revisión de fuente del 24 de octubre, posterior al primer hito `96c50eb`. La pista recuperada de Última Milla es `APT awscli → groff → Recommends ImageMagick`; el coordinador informa que una salida del 12 de octubre ya no mostraba ImageMagick/OpenEXR/libheif y SQL seguía active/enabled. [Conversación histórica indicada](https://chatgpt.com/c/6ac86dd2-7c2c-83e8-8968-9d65f1772704?messageId=ff7a1670-df79-4cef-a1fb-88d7100db4d7). Es evidencia de otro proyecto aportada por el investigador, no inventario ECS ni verificación directa de esta revisión.

**Hallazgo confirmado en ECS:** ambos bootstraps instalan `awscli` mediante APT sin `--no-install-recommends`. La configuración APT y las versiones del host pueden alterar el resultado. Por tanto aplica la posibilidad de incorporar recomendaciones innecesarias; **la cadena transitiva concreta y los paquetes efectivamente instalados en ECS siguen desconocidos**. Las consultas públicas a las fichas Ubuntu awscli/groff no devolvieron contenido en esta revisión; no se sustituyen por una cadena inventada. La [documentación oficial de apt-get](https://manpages.ubuntu.com/manpages/jammy/man8/apt-get.8.html) confirma el propósito de `--no-install-recommends` y la simulación `-s`, no el inventario de ningún host.

| Área | Estado de aplicabilidad | Fuente comprobada / límite | Corrección propuesta, sin ejecución |
| --- | --- | --- | --- |
| APT awscli y recomendaciones | APLICA al código; instalación transitiva DESCONOCIDA | `terraform/infra/data/user_data.sh:27`; `operations/sql-backup/recovery/bootstrap.sh:194` | Mantener CLI necesaria para S3/Secrets; probar instalación explícita mínima sin Recommends, no quitar awscli ni sustituir distribución sin cualificar |
| ImageMagick/OpenEXR/libheif/groff | DESCONOCIDO en ECS | No son solicitudes directas en los dos scripts SQL; no se leyó dpkg del host | Inventario/versiones/origen y dependencia inversa antes de cualquier eliminación; una biblioteca instalada no demuestra CVE explotable |
| Herramientas base | APLICA | Normal: curl, ca-certificates, gnupg, lsb-release, software-properties-common, awscli; recuperación omite las dos últimas utilidades antes de awscli | curl/certificados/gpg tienen uso visible; lsb-release y software-properties-common no tienen consumidor visible en ese script, que escribe repos directamente. Candidatas a omitir de nueva imagen, no purga ciega de host |
| SQL/ODBC | APLICA | Normal instala mssql-server y mssql-tools18/unixodbc-dev; recovery también comprueba msodbcsql18 y origen de candidatos | Conservar motor, sqlcmd y driver requerido; evaluar omitir sólo unixodbc-dev si el grafo real no lo requiere. Probar bootstrap, consulta, backup/restore y API antes de aceptar |
| AMI y versiones | APLICA; contenido actual DESCONOCIDO | `ordinary-main.tf:2` usa protected_sql_ami y omite cambios AMI en lifecycle; APT selecciona candidatos, no fija todas las versiones | Registrar AMI/owner/arquitectura y manifiesto final de paquetes. Actualización deliberada de imagen y recreación cualificada; digest AMI no congela descargas APT posteriores |
| Privilegios SQL | APLICA | `user_data.sh:127` concede db_owner; línea 122 CHECK_POLICY=OFF; `Program.cs:87` migra al inicio | Separar migrador de principal runtime con permisos de datos mínimos, verificar política de contraseña compatible con secretos generados. Probar despliegue blue/green y rollback sin cambios destructivos de esquema |
| Secretos | APLICA, con controles existentes | Bootstrap usa Secrets Manager, no tracing; SQLCMDPASSWORD y unset; output de conexión enmascara Password | Preservar metadata/valor fuera de state. Revisar exposición por entorno/proceso/log de error con pruebas de redacción; no leer valores para auditar. No afirmar fuga sólo por uso de variable de entorno |
| IAM | APLICA a fuente; efectivo vivo DESCONOCIDO | `terraform/infra/security/modules/protected_resources/main.tf.json` separa SQL secrets, task KMS y execution connection-secret por ARN | Conservar separación; comparar acciones contra uso real, boundaries y key policies al preflight autorizado. Nombres y simulaciones no prueban alcance efectivo; no administrar globalmente para evitar callbacks |
| Red/TLS | APLICA | SQL sin IP pública/IMDSv2 en ordinary-main.tf; bootstrap normal usa sqlcmd -C, conexión exportada TrustServerCertificate=True; ALB HTTP documentado | Cotejar SG real en siguiente plan y limitar SQL al consumidor. TLS SQL con validación de identidad es un cambio acotado distinto de PKI entre microservicios. No trasladar loopback del ensayo az6 al SQL de Fargate |
| Imagen API | APLICA con medidas existentes | `demo-api/Dockerfile`: runtime/SDK por digest, multi-stage, USER APP_UID; sólo publish a runtime | Escanear digest final y SBOM fechado, no sólo SDK; preservar non-root y no instalar compiladores en runtime. Pin no significa libre de vulnerabilidades |
| NuGet directo/transitivo | APLICA; CVEs actuales DESCONOCIDAS | API: AWS SDK, MediatR, EF10.0.13, Pkcs10.0.13, Swashbuckle6.6.2 y tooling; backup: SqlClient6.1.7, Pkcs y AWS S3/STS. Restauración API sin lock | Capturar grafo resuelto/SBOM, revisar avisos oficiales por versión y uso; probar actualizaciones focalizadas. Distinguir tooling de build de DLL efectivamente publicada. No declarar vulnerable por antigüedad o nombre |
| Controles PKI de servicios | NO APLICA al alcance ECS acordado | Una API, sin segundo servicio de negocio | Conservar exclusión; no crear otro servicio para justificar seguridad |
| Inspector/Security Hub | NO ACTIVADO por esta revisión | No consultas AWS ni habilitación de servicios | No necesarios para este primer cierre proporcional; cualquier evaluación cloud posterior requiere alcance/coste propios |

### Cambio mínimo recomendado y prueba de preservación

Preparar después un cambio de bootstrap, no un script de purga: separar la instalación base de `apt-get install -y --no-install-recommends awscli` en ambos bootstraps. Éste es el primer cambio mínimo recomendado. Evaluar el mismo tratamiento para SQL y la omisión de unixodbc-dev en un cambio posterior, sólo con grafo y prueba nativa; cualquier simulación debe usar las mismas opciones de su instalación. Mantener fuentes Microsoft firmadas y comprobación de candidatos. No usar `autoremove` general, regex de purga ni borrar librerías por nombre; no modificar los artefactos históricos cualificados.

La primera regresión local verificará argumentos reales/simulación y que permanecen CLI, certificados, SQL/ODBC y controles de origen. Esa prueba de fuente no acredita resolución APT ni SQL nativo. La cualificación posterior necesita Ubuntu/AMI y repos concretos: manifiesto dpkg de nombre/versión/arquitectura, apt-cache Depends/Recommends y política de candidato, configuración Install-Recommends, simulación antes/después y un inventario de librerías del runtime. Guardar sólo metadatos, nunca secretos. En un host desechable autorizado: servicio SQL active/enabled, consulta autenticada, backup/restore/CHECKDB y lectura/escritura/descifrado API. Comparar superficie y versiones, no exigir un número artificial de cero findings.

Prioridad: (1) instalación mínima reproducible y evidencia de dependencias; (2) separar privilegios de migración/runtime y validar TLS SQL; (3) mantener análisis de imagen/NuGet y actualización dirigida por riesgo comprobado. No se confirmó CVE, instalación de los paquetes sospechosos ni causa raíz de una vulnerabilidad ECS en esta revisión. El hallazgo causal completo de Última Milla podrá añadirse sin convertirlo en prueba de ECS.

### Cotejo final con la investigación histórica

El investigador recuperó la [retirada exacta de diez paquetes y comprobación SQL](https://chatgpt.com/c/6ac03927-1efc-83e8-9828-0d23dc500245?messageId=1950c572-0fe9-496e-a3b8-e6c267514183) y la [corrección de receta con cuatro regresiones](https://chatgpt.com/c/6ac03927-1efc-83e8-9828-0d23dc500245?messageId=4f40135f-4c5f-4e11-b2c3-cc8557c04573). Kendall precisó que él retiró manualmente esos paquetes; no fue una limpieza automática del bootstrap. Según esa evidencia aportada, la retirada preservó CLI, SQL active, puerto1433 y SELECT1; no hubo prueba de recreación AMI. En ECS sólo queda confirmado el mismo patrón de instalación, no aquellos diez paquetes. Residuos dpkg `rc` no equivalen a paquetes instalados.

La [regresión al revertir el hardening para desbloquear CD](https://chatgpt.com/c/6ac86dd2-7c2c-83e8-8968-9d65f1772704?messageId=b98b85e3-3aa4-488b-9274-8547f0173edf) refuerza separar receta, artefacto, apply y runtime: no revertir seguridad para obtener un plan sin diferencias. La [denegación NAT contextual](https://chatgpt.com/c/6ac86dd2-7c2c-83e8-8968-9d65f1772704?messageId=4e7f3ee7-f4d9-417c-aeaf-1cee25fa7024) aporta un método, no un permiso aplicable a ECS: comprobar principal efectivo y contexto, conservar negativos y no presentar mocks/admin como ejecución del workload. El resumen histórico de kernel/reboot contiene versiones contradictorias; no se utiliza para afirmar kernel vulnerable ni actualizado en ECS. En una cualificación futura, separar versión de paquete instalada de kernel cargado y postchecks tras reinicio autorizado.

**Camino crítico proporcional:** cerrar primero la receta CLI mínima y sus regresiones; después cualificar el artefacto/host y recuperación desde cero. Clasificar los controles actuales de imagen por digest/non-root y secretos fuera de state como implementados en fuente; API sencilla y una SQL como límites aceptados de demo; paquetes transitivos, TLS SQL, permisos de migración y observador AWS como pendientes de cualificación/corrección. No convertir esa clasificación en aceptación de vulnerabilidades desconocidas. El cierre de diseño de hoy no depende de activar escáneres de pago ni de perseguir cero findings.
### Precisión del propietario y cobertura de todas las instalaciones

Kendall confirma que la ausencia posterior de paquetes gráficos en Última Milla se debió a su **retirada manual**, y señala las recomendaciones aceptadas por el User Data como origen a corregir. No atribuir esa limpieza a automatismos ni extrapolar la cadena histórica awscli como única causa posible en ECS.

El cotejo de los scripts shell, plantillas y Dockerfiles versionados encontró estos puntos APT relevantes; ninguno fija `--no-install-recommends` ni una política Install-Recommends en esas fuentes:

| Ruta y línea en la base revisada | Operación | Tratamiento recomendado |
| --- | --- | --- |
| `terraform/infra/data/user_data.sh:27` | Base: curl, CA, gnupg, lsb-release, software-properties-common, awscli | Separar CLI y revisar recomendaciones de todos los paquetes base, no sólo awscli |
| mismo archivo:83 | mssql-server | Comparar grafo con/sin recomendaciones y probar instalación/configuración nativa antes de cambiar opciones |
| mismo archivo:99 | mssql-tools18, unixodbc-dev | Conservar sqlcmd/driver necesarios; distinguir dependencias obligatorias, recomendaciones y paquete dev pedido explícitamente |
| `operations/sql-backup/recovery/bootstrap.sh:134` | Motor, tools y unixodbc-dev | Aplicar la misma política cualificada que al bootstrap normal; no dejar una ruta que reintroduzca extras |
| mismo archivo:194 | Base: curl, CA, gnupg, awscli | Mismo criterio de base mínima |
| mismo archivo:199 | Simulación APT de paquetes SQL | Mantener argumentos equivalentes a la instalación real tras cualquier cambio |

Los `apt-get update` sólo actualizan índices. Los Dockerfiles revisados no añaden instalaciones APT, pero eso no acredita ausencia de paquetes heredados de sus imágenes base. La búsqueda de fuente tampoco descubre la configuración APT de una AMI, scripts externos o un host modificado manualmente. La corrección de origen propuesta cubre **todas** las instalaciones anteriores: política explícita de recomendaciones, lista directa justificada y comprobación del grafo resuelto, preservando Depends y componentes SQL/ODBC requeridos. Separar awscli es un primer cambio pequeño, no cierre de toda la superficie. No se ha cambiado ninguna receta ni desinstalado nada en este encargo de diseño.

### Ventana de revisión LIVE del próximo ciclo

Nueva condición del propietario: reservar una ventana para que Kendall vea ECS funcionando y avisarle **antes de retirar**. El plan del siguiente ciclo autorizado debe incluir esa ventana dentro de su presupuesto y plazo, además de la reserva de limpieza; no comienza ningún despliegue por esta anotación.

Recomiendo reservar 30 minutos de demostración después de readiness y pruebas mínimas, ajustados al cálculo de coste del plan. Avisar al llegar a ese estado con enlace accesible, alcance realmente LIVE y hora prevista de retirada. Mostrar web, diagramas existentes y recorrido por API/infra/avisos efectivamente probados; una web sintética o diagrama histórico no se etiqueta como backend vivo. El diagrama final conjunto aplazado no se reactiva por esta condición.

Si Kendall no responde, mantener sólo la ventana presupuestada y retirar a tiempo; avisar del cierre y conservar evidencias para revisión posterior. No esperar indefinidamente ni consumir la reserva de teardown. Si un fallo impide llegar a LIVE o el presupuesto no deja margen, comunicar qué falló y retirar conforme al plan, sin inventar disponibilidad ni reiniciar el presupuesto. La siguiente aprobación debe mostrar esa ventana junto al coste total y la retirada, sin introducir un corte corto dependiente de un like.
### Incremento local aplicado: CLI sin recomendaciones

Después de la revisión, el propietario autorizó este fix acotado de código. Ambos bootstraps separan ahora `apt-get install -y --no-install-recommends awscli` de los paquetes base. Recovery registra la etapa `aws_cli` y aborta antes de obtener secretos si falla. Se conservan los consumidores Secrets Manager SA/app, SQL, tools y ODBC; no hay purga ni cambio de opciones en las instalaciones SQL/base restantes. Las observaciones anteriores describen la base revisada, no niegan esta corrección posterior.

Cuatro regresiones nuevas en `operations/sql-backup/recovery/test_bootstrap.py` ejecutan las líneas CLI reales con comandos interceptados, verifican argumentos/orden y aborto, y ejercitan ambos helpers de Secrets Manager con respuestas sintéticas. Suite final: **27 PASS**; `bash -n` de ambos scripts y `git diff --check` PASS. Primera ejecución: 26 PASS y una prueba previa falló por aviso de Git Bash `could not find /tmp`; una repetición completa pasó sin cambiar ni silenciar la aserción. No se instaló APT, accedió a AWS ni ejecutó SQL nativo.

Esto cualifica receta y contratos de consumo, no dependencias resueltas de Ubuntu ni ausencia de paquetes gráficos en runtime. Pendiente: grafo APT del host/imagen, otras recomendaciones base/SQL y prueba nativa de instalación/consulta/backup/restore. No se reconstruyeron ni modificaron los artefactos históricos: cualquier próximo artefacto debe identificar este nuevo código y cualificarse antes de uso.
