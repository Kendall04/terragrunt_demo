# V2 — revisión de arquitectura y pipelines

**2026-10-16 · Solo análisis; recomendaciones, no instalación ni autorización AWS.**
Base V1 preservada: `061710aded14d4716e7488073a2da5387395e0a0`;
rama `feat/v2-architecture-review`. El proyecto continúa: este encargo abre el
diseño de durabilidad antes pospuesto por D5. **Mantener / Modificar / Eliminar /
Añadir** clasifican propuestas futuras; no se elimina historia, código o recursos.

## 1. Arquitectura actual y evidencia

Fuentes: [contratos y topología](architecture.md), [raíces DEV](../modules/target/dev),
[entrega real](deployment.md#real-sourcetransport-qualification-and-distinct-digest-dev-rollback),
[recuperación NAT](e13-nat-reliability.md#installed-dev-correction-and-automatic-b-retrial)
y [DOWN final](e16-practical-dev-lifecycle.md#final-real-dev-down-completed--2026-10-16-utc).
La última observación V1 documentada dejó el runtime apagado, cinco estados vacíos
y E2 generation 14 RELEASED. **Esta revisión no hizo consultas AWS nuevas.**

| Plano | Implementación y límite comprobable |
| --- | --- |
| Red | Una VPC; dos subnets públicas y dos privadas en dos AZ; IGW; dos NAT EC2 t3.micro/ASG/EIP. El código elige las dos primeras AZ disponibles, no nombres estables explícitos. |
| Entrada y aplicación | API Gateway HTTP API → VPC Link → ALB interno HTTP:8080 → ECS Fargate privado. Dos servicios blue/green; Terraform los inicia a cero, WP4 controla revisiones, réplicas y tráfico. Por defecto hay una tarea activa de 0,25 vCPU/512 MiB, no una por AZ. |
| Datos | SQL Server 2022 Express/Ubuntu 22.04 x86-64, EC2 t3a.small en `private_subnet_ids[0]`; datos en root EBS gp3 cifrado de 30 GiB con `delete_on_termination=true`. No backup/restore ni réplica SQL demostrados. |
| Dependencias | KMS, tres secretos, ECR, S3, Lambda, EventBridge, SQS/DLQ, CloudWatch y SSM. No Cloud Map. Terraform conserva esqueletos; E13 posee los efectos NAT, WP4 los de aplicación y E16 las cinco escrituras de estado DEV. |
| Demostrado | Reconstrucción completa, SQL/KMS, OIDC/WP3/WP4, promoción/cleanup, rollback entre dos digests distintos y reemplazo NAT de ambos slots. Rollback de imagen no restaura una base de datos. |

**Riesgos reales:** pérdida de SQL/root EBS; indisponibilidad de su única AZ;
una sola tarea; ausencia de backups; migraciones al arrancar con `db_owner`;
API pública sin autenticación; TLS SQL con `TrustServerCertificate=True`;
HTTP interno; egress amplio. `/ready` valida dependencias al desplegar, mientras
ALB usa liveness: una tarea sana no garantiza que SQL/KMS sigan disponibles.
El fallo inicial NAT B y la incertidumbre histórica aceptada para aquel DOWN
permanecen diferenciados del ensayo automático corregido; no son éxitos ficticios.

## 2. Decisión sobre AZ, disponibilidad y SQL

| Acción | Alternativa | Decisión recomendada |
| --- | --- | --- |
| **Mantener** | Dos AZ y arquitectura original | Sí. Conservan separación de egress, ALB/VPC Link y espacio para redundancia ECS. Priorizar recuperación de datos. |
| **Modificar** | Dos réplicas activas durante un ensayo HA de aplicación | Opcional, por sesión: observar distribución efectiva y caída de una tarea/AZ. Dos subnets no fuerzan dos réplicas ni prueban HA integral. |
| **Eliminar** | Tercera AZ del alcance V2 inicial | No añade disponibilidad efectiva a SQL ni a una tarea única; exigiría ampliar módulos de cuatro subnets/dos slots, capacidad, pruebas y costos. |
| **Mantener / Modificar** | SQL Express en EC2; añadir recuperación desde S3 | Mantener motor y EC2; modificar la estrategia de datos. Restaurar en otra AZ es recuperación con interrupción, no failover automático. |

**HA** mantiene servicio redundante; **failover** cambia al sustituto;
**backup/restore** recupera un punto anterior. E13 repone un NAT en su slot/AZ,
sin continuidad ni failover entre AZ garantizados. Separar datos del root EBS
mejora su ciclo de vida, no su alcance zonal. Express no aporta availability
groups/log shipping soportados: no inventar una réplica ni cambiar a RDS/otra edición.
[Microsoft: límites de Express en Linux](https://learn.microsoft.com/en-us/sql/linux/sql-server-linux-editions-and-components-2022?view=sql-server-ver16).
Para ECS, verificar configuración y distribución reales antes de afirmar balanceo;
[AWS documenta el reequilibrio y sus requisitos](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service-rebalancing.html).

## 3. Auditoría de los 27 workflows y propuesta CI/CD

| Acción | Entradas actuales | Tratamiento V2 |
| --- | --- | --- |
| **Mantener** | `ci.yml` + `ci-dotnet.yml`, `ci-repo-hygiene.yml`, `ci-terragrunt.yml` | Una entrada CI en push/PR con selección conservadora, tests, Docker, formato, seguridad y resultado obligatorio; sin credenciales AWS para CI ordinaria. |
| **Modificar** | `ci-cd-safety.yml`, `cd-scope.yml` | Integrar la validación CD Safety como job obligatorio de CI si elimina duplicación de triggers. Conservar sus tests, alcance fail-closed y check efectivo; scope puede seguir como helper. |
| **Mantener** | `release-build.yml` → `e1-release.yml` | Calificación WP3 y publisher autorizado, digest/manifest/hash/VersionId y siete controles. CI de PR y WP3 tienen fronteras de confianza distintas: repetir pruebas no es automáticamente redundante. |
| **Mantener** | `deploy-dev.yml` y `rollback-manifest.yml` → `e1-dev-deploy.yml` | Dos entradas manuales claras: release elegible o historia SUCCESS elegible. Conservar E2, readiness por réplica, promoción y cleanup reales. |
| **Eliminar** | `cd.yml`, `cd-demo-api.yml` como entradas activas del repositorio limpio | Orquestación superpuesta y bloqueada por infraestructura inactiva/dependencias de develop; no es el camino demostrado de aplicación. Retirar solo tras verificar referencias y contratos, no activar sus rutas PROD. |
| **Modificar** | `ci-terragrunt-manual.yml`, `ci-terragrunt-plan.yml`, `cd-terragrunt.yml` y seis `e1-{plan,infra,infra-high-risk}-{dev,prod}.yml` | Hoy son wrappers/templates protegidos inactivos. Mantener E16 supervisado para DEV, planes guardados y locking; no instalar WP5 para sustituirlo. En V2, una guía/entrada de infraestructura inequívoca, no tres menús que parecen operativos. |
| **Eliminar / Mantener** | `cd-rollback.yml`, `e1-dev-emergency.yml`, `e1-prod-emergency.yml`, `promote-prod.yml`, `e1-prod-promote.yml` | Archivar las entradas públicas inactivas en la presentación limpia; conservar los contratos avanzados necesarios. Emergency recovery no equivale al rollback de release que sí se probó. Ninguna ruta PROD se activa. |

Destino: **CI → release → deploy DEV → rollback**, con infraestructura E16 aparte.
Reutilizar WP3/4. Proponer `main` + PRs sin alterar `develop` V1. **Modificar**
repositorio/ref/audience STS/Environment/pin de los dos request roles solo con las
admisiones/instalación existentes. Hoy solo está demostrada
`codex/final-github-actions-cicd` con pin
`f0ba8ad1d6528d362693c8de932f935c8084529d`; renombrar YAML no habilita main ni otro repo.
Mantener OIDC sin access keys, roles request sin escritura de estado, workers y
publisher acotados, PassRole exacto, E16 exclusivo y revisión real de PR.
No borrar templates ni fixtures mientras generators/tests/inventario los referencien.

## 4. Backups SQL: diseño pequeño y restauración verificable

**Añadir** un flujo nativo `.bak` local → S3 privado; **Mantener** SQL Express.
Express no incluye SQL Agent, compresión/cifrado nativo de backups ni el conector
S3 de `BACKUP TO URL`; usar CLI/SDK con rol EC2, nunca access keys en credenciales
SQL. Fuentes: [ediciones](https://learn.microsoft.com/en-us/sql/sql-server/editions-and-components-of-sql-server-2022?view=sql-server-ver16),
[restricción S3 Express](https://learn.microsoft.com/en-us/sql/relational-databases/backup-restore/sql-server-backup-to-url-s3-compatible-object-storage?view=sql-server-ver16).

| Acción | Opción | Evaluación |
| --- | --- | --- |
| **Añadir** | systemd timer + script versionado en SQL EC2 | Recomendada para un host Linux: una ejecución local a la vez, deadline, salida verificable y captura de fallos; sin scheduler distribuido. |
| **Mantener** | SSM Run Command | Mismo script para backup/restore supervisado. Una asociación State Manager puede reemplazar al timer si se necesita control central, pero no programar ambos. |
| **Eliminar** | AWS Backup/EBS snapshots como única prueba SQL | Pueden complementar recuperación de host; un snapshot sin quiescencia no demuestra integridad SQL. La vía VSS documentada es Windows, no este Linux: [AWS Backup](https://docs.aws.amazon.com/aws-backup/latest/devguide/windows-backups.html). |

Propuesta pendiente de aceptar: full cada hora durante UP; hourly de 48 h y un
full diario de 7 días, prefijos distintos. **RPO objetivo ≤ 1 h + duración de
backup/subida; RTO objetivo ≤ 60 min** hasta SQL/aplicación funcionales para DB
pequeña; medir, no prometer SLA. Sin log backups no hay point-in-time restore:
elegir SIMPLE explícitamente para la demo o diseñar la cadena de logs para FULL.
Un timer perdido no reconstruye cambios perdidos; tamaño y duración condicionan el diseño.

1. **Añadir:** `BACKUP DATABASE ... TO DISK ... WITH CHECKSUM, STOP_ON_ERROR`;
   sin compresión ni opciones de cifrado no soportadas. Guardar temporalmente en
   EBS cifrado, directorio restringido, comprobar espacio antes de empezar y
   limpiar solo archivos propios después del compromiso remoto. Los 30 GiB
   actuales no garantizan espacio para datos, log y `.bak`: medir y revisar tamaño
   o staging antes del plan. No imprimir passwords, texto ni connection strings.
2. **Añadir:** subir con nombre único; verificar SHA-256, tamaño y VersionId, y
   publicar manifest de finalización solo tras verificar el objeto. Conservar
   versión SQL, DB, tiempos y referencia a la clave de datos; ETag no es SHA-256.
   Resolver un timeout mediante readback exacto, no declarar éxito ni reenviar a
   ciegas. Un archivo completo local no es todavía un backup remoto exitoso.
3. **Añadir:** `RESTORE VERIFYONLY WITH CHECKSUM` y restauración real separadas.
   VERIFYONLY no restaura ni comprueba toda la estructura: [Microsoft](https://learn.microsoft.com/en-us/sql/t-sql/statements/restore-statements-verifyonly-transact-sql?view=sql-server-ver16).
   Usar usuario `db_backupoperator` para BACKUP; verificación/restore necesitan
   contexto SQL separado con permisos adecuados, no elevar al usuario de aplicación.
4. **Añadir:** bucket dedicado fuera del DOWN runtime: Block Public Access, TLS,
   versionado, SSE-KMS y una clave de backup retenida con permisos independientes.
   Conservar además la clave KMS original de los textos: recuperar SQL sin ella
   deja ciphertext ilegible. Lifecycle explícito para hourly/daily, versiones no
   actuales y multipart incompletos; expiración eventual, no borrado exacto a la hora.
5. **Añadir:** gateway endpoint S3 en ambas route tables privadas, políticas de
   endpoint/bucket restringidas al backup y roles; sin endpoints de interfaz por
   defecto. [No tiene cargo adicional de endpoint](https://docs.aws.amazon.com/vpc/latest/privatelink/gateway-endpoints.html);
   S3/KMS/requests siguen cobrando. Secrets, SSM y otras APIs aún pueden necesitar NAT.
6. **Añadir:** IAM productor con `s3:PutObject/GetObject` de su prefijo para subida
   y readback; multipart requiere sus permisos de partes/abort; `ListBucket` solo
   si el flujo lo necesita y con prefix. `kms:GenerateDataKey/Decrypt` limitado a
   esa clave vía S3/contexto compatible, incluido multipart. Restore tiene
   `GetObjectVersion` y Decrypt; no DeleteObject ni permisos backend/PROD. Secretos
   SQL por ARN exacto, valores fuera de Terraform/argv/logs. Revisar policies antes
   de instalarlas; esta propuesta no concede privilegios.
7. **Añadir:** último backup remoto exitoso, error y antigüedad; alarma por fallo
   o ausencia >2 h mientras se espera DEV UP. Una instancia caída no puede anunciar
   su propio fallo: observar ausencia desde CloudWatch/SSM externo. Canal humano
   real requiere destinatario autorizado; no suponer que SNS entrega emails.

**Añadir** restore drill por SSM en otra EC2/AZ con SQL compatible, sin sobrescribir
la DB original: VersionId/hash exactos, `RESTORE ... WITH MOVE`, `DBCC CHECKDB`,
login/usuario/SID y permisos correctos, lectura/decrypt de registro conocido.
Verificar `/ready` y POST/GET con app aislada antes de migrar; registrar tiempos/RPO,
sin filas ni secretos. El posterior ensayo autorizado de pérdida del host prueba
el runbook, no VERIFYONLY ni rollback de imagen. Backup final y pérdida de datos
antes de DOWN siguen sujetos a decisión explícita.

## 5. Integración Service Identity PKI

**Mantener** paquetes del proyecto independiente, no copiar framework. Snapshot
local `29a3dfc70a0b1646388c0229212898b4be164afe`: seis `ServiceIdentity.Pki.*`
`0.1.0-alpha.1` en feed local, no NuGet público asumido. MVP local: `Providers.Local`
e `Integration.AspNetCore`, Core transitivo. APIs: `AddServiceIdentityPki`,
`Configure`, `OpenClient`, `Prepare/Activate`, leases por generación.
`Rotation` opcional; `Rotation.Sqlite` no sirve como backend multi-host ECS.
`Providers.Aws` está probado offline, no productivamente. Código/contrato público
y evidencia fase 5 prevalecen sobre el README ASP.NET parcialmente histórico.

**Añadir, condicionado:** servicio privado `text-vault` reutilizando persistencia/KMS,
llamado por la API vía mTLS sin cambiar HTTP exterior ni contratos SQL/KMS.
Un consumidor de prueba basta para mTLS cliente; servicio-a-servicio exige segundo
proceso real. SQL/TDS cifrado no es mTLS ASP.NET. Preferir dos servicios ECS con
roles distintos: sidecars comparten task role/fallo. **Añadir** discovery privado
mínimo (ECS/Cloud Map, ausente en V1) solo al aceptar esa separación. WP4 cierra
familias/contenedores de una API; admitir vault/readiness requiere cambio acotado,
no compatibilidad automática ni plataforma genérica multiservicio.

**Modificar / Añadir:** dos identidades URI canónicas propias, perfiles separados
cliente/servidor, CA/trust explícitos, DNS/EKU/KU/vigencia y allowlist por operación.
Conexión directa privada entre servicios; atravesar ALB termina TLS y no prueba
mTLS de extremo a extremo. HTTPS a targets tampoco valida sus certificados:
[AWS ALB](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/load-balancer-target-groups.html).
La seguridad SQL requiere además cert/DNS y validación del driver propios.

**Gate AWS pendiente:** claves leaf por réplica en RAM, CSR ligada a identidad de
workload autenticada, firma mediante el proveedor existente y certificados públicos
versionados; nada de keys en imagen/state/log. KMS SIGN_VERIFY custodia la clave
firmante, no sirve como private key TLS de Kestrel. El framework aún no resuelve
enrollment remoto autenticado, recuperación de custodia ni revocación productiva;
su fachada exige `LocalDevelopment`. Resolver/calificar esos puntos en PKI antes
de prometer rotación ECS. No camuflarlos con un perfil de producción ni clonar
un emisor/coordinador en este repo. Publicación/licencia del feed también es gate.

**Añadir** ensayo de rotación por réplica: carga continua, handshakes nuevos,
fingerprints TLS reales, rechazos CA/identidad/expirado y métricas de errores.
Objetivo cero fallos en ensayo acotado: timeout < drain y renovación antes de
expirar. Las conexiones que exceden drain pueden cerrarse: sin garantía ilimitada
ni prueba basada solo en ACK. CA rollover requiere ensayo distinto.

## 6. Reliability Sentinel: observación primero

**Añadir** integración por contrato del proyecto independiente, snapshot local
`0e8fc55333ddde3b9816885915310a7e69f3de45`, sin copiar Core ni instalar su blueprint
completo por defecto. Su `NativeEventNormalizer` admite CloudWatch Alarm, EC2 y
ASG con catálogo exacto; `ServiceCatalog` exige actualmente `mechanism=nat-asg`.
La ruta custom existente usa `sentinel.synthetic`: no enviar fallos reales bajo
una identidad sintética para aparentar integración. Los hosts probados en AWS
son de Ohio; hay composición parametrizable y workers legacy fijados a esa región.
Validar la entrada efectiva en `us-east-1` antes de cualquier instalación local.

| Acción | Señal / conexión | Límite y responsabilidad |
| --- | --- | --- |
| **Añadir** | NAT A/B: eventos ASG/EC2, alarmas, receipts E13 y egress reciente | Primer Shadow acotado, bindings nuevos tras UP. Correlacionar intento/instancia/slot/EIP/ruta, no inferir recuperación por RUNNING/InService. E13 es el único remediador. |
| **Añadir, pendiente upstream** | ECS/WP4: task/deployment/digest y receipts; SQL: readiness; backup: éxito/edad/hash/restore | Nuevos adaptadores/catálogo de esos dominios; no modelarlos como NAT. Empezar con replay de eventos sanitizados y alarmas nativas independientes. |
| **Añadir, pendiente upstream** | PKI: expiración, fallo de enrollment, generación y evidencia TLS | Metadatos sin certificado privado ni payload; correlación por servicio/réplica/tiempo. Sentinel no emite, rota ni revoca certificados. |

**Mantener** IDs estables, esquema/política, cuenta/región, tiempos y frescura,
deduplicación y UNKNOWN ante evidencia insuficiente; correlación no es causalidad.
IAM solo observación, sin mutar ASG/rutas/ECS/SQL/E2/E13; escribir solo storage propio.
Comenzar sin probes/notificaciones; el Notify actual es fake. Canal humano y sonda
privada requieren validación posterior. Vigilar backlog y mantenimiento DOWN sin
heartbeat ficticio. Backup/alarma básica no dependen de Sentinel.

## 7. Seguridad y aprendizajes PCI, sin afirmar certificación

Lectura de informes privados de hardening/pipelines y secretos/state de Última
Milla: separar instalación inerte de activación funcional; aprobar planes conocidos,
acotar scope y verificar artefacto, dependencias y custodia. Son lecciones de
ingeniería, **no certificación PCI DSS ni prueba de este lab**. Ningún extracto,
código, identificador, configuración o dato empresarial se incorpora al repo público.

| Prioridad / acción | Mejora propia de este proyecto |
| --- | --- |
| P0 **Modificar** | Antes de una UI LIVE pública: autenticación/autorización real de lectura/escritura y cuotas; JWT authorizer con issuer/audience escogidos, sin inventar otro IdP. La UI sintética no necesita acceder a AWS. |
| P0 **Modificar** | Separar migrador del usuario SQL runtime, retirar `db_owner` de la app; validar hostname/cadena SQL y quitar `TrustServerCertificate=True` solo cuando exista cert válido. Inventariar HTTP interno como límite de confianza, no afirmar cifrado extremo a extremo. |
| P1 **Modificar / Mantener** | Documentar flujos de datos y límites usuario/edge/servicios/SQL/backups/control. Egress por destino necesario, SSM sin SSH público, IAM mínimo/OIDC/PassRole/locks y separación de secretos metadata/valor. No mezclar autoridad del observador y remediador. |
| P1 **Modificar** | Planificar actualización del runtime/SDK/base images y probar compatibilidad PKI: [.NET 8 termina soporte el 2026-11-10](https://devblogs.microsoft.com/dotnet/dotnet-8-9-end-of-support/). No se actualiza aquí ni se asume compatibilidad con .NET 10 sin tests. |
| P1 **Añadir** | Evidencia de scanning/SBOM/dependencias y política de severidad/procedencia antes de promoción; logs estructurados con trace/deployment/attempt IDs, sin bodies, claves, tokens o connection strings. Datos de auditoría con acceso/retención definidos. |

Inventario histórico exacto, no scanner ejecutado en esta fase:
[baseline por identidad/multiplicidad](../../.github/scripts/ci/static-findings.json).

| Acción / prioridad | Hallazgo | Cantidad | Clasificación y siguiente comprobación |
| --- | --- | --- | --- |
| **Modificar**, P1 | tfsec `AVD-AWS-0030`, HIGH | 18 | Reporta scanning ausente, pero los recursos ECR fuente ya tienen `scan_on_push=true`. Resolver lectura/representación y obtener resultado de scan real; no afirmar 18 repos vulnerables. |
| **Modificar**, P1 | `AVD-AWS-0088` HIGH / `0090` MEDIUM | 7 + 7 | Fuente declara cifrado y versionado en recursos separados; el inventario V1 observó seis buckets cifrados/versionados. Contradicción con el scanner, no prueba de ausencia. Analizar cada identidad/generación antes de clasificar falso positivo. |
| **Modificar**, P1 | `AVD-AWS-0132`, HIGH | 7 | SSE-S3 no es CMK. Decidir KMS por sensibilidad/rol; backup nuevo sí requiere SSE-KMS. Migrar todos los buckets indiscriminadamente cambia permisos/costos protegidos. |
| **Añadir / Modificar**, P2 | `AVD-AWS-0089`, MEDIUM | 7 | Falta logging S3 en la declaración: definir auditoría útil de acceso y retención. CloudTrail de management no cubre por sí solo todos los accesos a objetos; data events/access logs tienen costo. |
| **Modificar**, P2 | TFLint required_version / required_providers / deprecated_index / unused_declarations | 7 / 2 / 1 / 14 | 24 warnings de mantenimiento/reproducibilidad; corregir en fuente/generadores, incluidas referencias que impidan retirar variables. Revisar cualquier efecto PROD por separado. |

Total: **46 tfsec / 24 TFLint**, no 46 defectos explotables confirmados. Ni ocultar
hallazgos ni refrescar la baseline a ciegas: exigir evidencia de remediación y revisar
el delta por identidad/multiplicidad. P0 incluye riesgos que esos scanners no detectan.

## 8. UI, Archify y futuro repositorio limpio

**Añadir** Product Demo/Architecture Explorer siguiendo Parcel de EKS, cuyo código
es React/TypeScript/**Vite**: Parcel es el nombre, no el bundler. DEMO sintética
explícita, separada de LIVE, sin fallback falso tras fallo real. Explorer público:
evidencia sanitizada con fecha/fuente/hash, estados histórico/observado/stale/no
verificado, sin credenciales/endpoints privados. LIVE depende del P0 de identidad.

**Añadir** exports HTML Archify revisados/pin por hash/licencia, `iframe` sandbox
con scripts pero sin `allow-same-origin`, sin tokens ni comandos entre origins;
Mermaid sigue como referencia rápida. Export local no implica hosting público ya
instalado. Adaptar presentación responsive y probar navegador/accesibilidad después.

**Mantener** app/contratos, módulos originales, locks, ownership, E16, WP3/4,
pruebas que protegen comportamiento y evidencia V1 sanitizada. **Eliminar** del
repositorio limpio solo duplicados históricos, PNGs superados y menús inactivos
sin consumidores. `ci/authority/retired` contiene bytes usados para procedencia/
generación: retirarlos exige resolver esas dependencias, no borrado en bloque.
No migrar ahora; conservar historia V1 íntegra y publicar paquetes con permisos/
licencias explícitos, no referencias a rutas locales privadas ni copias de frameworks.

## 9. Costos aproximados y límites

Estimaciones de diseño, sin factura/consulta AWS nueva ni presupuesto aprobado;
precios públicos consultados el 2026-10-16. Recalcular antes de otra sesión.

| Acción / alternativa | Impacto incremental aproximado |
| --- | --- |
| **Mantener** dos AZ | Conserva dos NAT/EIP/EBS, SQL, Fargate y ALB. USD 0,102/h es una estimación histórica V1, no una cotización V2 ni costo total con storage/requests. |
| **Modificar** a dos tareas activas, o **Añadir** vault mínimo | Por cada tarea Linux/x86 0,25 vCPU/0,5 GiB: ≈ USD 0,01234/h, ≈ USD 9/730 h, antes de tráfico/logs. Blue/green añade candidatos temporalmente; el nuevo servicio podría requerir mayor memoria tras medirlo. |
| **Eliminar** tercera AZ inicial | Evita otro NAT EC2/EBS/EIP y, para tres AZ efectivas de app, otra réplica. Cada IPv4 pública añade USD 0,005/h ≈ USD 3,65/730 h; red/subnets solas no justifican ese gasto. |
| **Añadir** backup | Hasta unas 55 generaciones full visibles con actividad 24/7 para 48 h hourly + 7 daily: tamaño B × generaciones × tarifa S3 regional, más versiones no actuales/expiración eventual/requests. Medir `.bak`, no suponer compresión; sumar staging EBS y EC2 temporal del restore. Una CMK adicional parte de USD 1/mes más requests/rotaciones aplicables. |
| **Añadir** PKI/Sentinel por etapas | Paquetes locales no implican consumo AWS. Live suma firma KMS, storage, Lambda/DynamoDB/SQS, alarmas y logs; discovery si se separan servicios. No trasladar estimaciones Ohio de Sentinel ni su presupuesto de ejemplo al lab. |
| **Eliminar** CA administrada del MVP | No incorporar AWS Private CA por defecto: referencia USD 50/mes short-lived o USD 400/mes general-purpose, más certificados/uso. La alternativa propia tampoco resuelve gratis custodia/enrollment. |

Fuentes de cálculo: [Fargate Virginia](https://aws.amazon.com/fargate/pricing/),
[IPv4](https://aws.amazon.com/vpc/pricing/), [S3](https://aws.amazon.com/s3/pricing/),
[KMS](https://aws.amazon.com/kms/pricing/) y [Private CA](https://aws.amazon.com/private-ca/pricing/).
El backup y las claves sobreviven DOWN dentro de la retención aprobada: cero
cómputo no significa cero cargos. No hay retención/budget automáticamente aprobados.

## 10. Dependencias y siguientes incrementos

| Orden / acción | Incremento acotado | Criterio para avanzar |
| --- | --- | --- |
| 1 **Añadir** | Backup/restore SQL, primero scripts y tests offline, manifests e IaC de bucket/CMK/endpoint/IAM mínimo | Rechazar checksum malo, upload ambiguo, falta de espacio, secreto en salida y restore sobre DB equivocada. Revisar RPO/RTO/retención y plan sin aplicar. Es el primer incremento recomendado. |
| 2 **Modificar** | P0 de identidad/TLS/roles y ruta de pipeline V2 | Decidir issuer/consumer, feeds/licencias y repo/ref; generar admisiones genuinas sin abrir trusts. Mantener V1 y estado exclusivo E16; revisar cambios protegidos antes de instalarlos. |
| 3 **Añadir** | Sesión AWS futura expresamente autorizada: reconstrucción, backup y restore en otra AZ | IDs/bindings nuevos, E13 validado, restore SQL/KMS funcional y RPO/RTO medidos. No resucitar el runtime como parte de esta revisión. |
| 4 **Añadir / Modificar** | Consumidor local PKI → gates upstream AWS → API/vault y rotación DEV | mTLS y autorización negativos/positivos reales, luego custodia/enrollment calificados; actualizar solo el alcance WP4 necesario. No depende de Sentinel. |
| 5 **Añadir** | Sentinel NAT Shadow, después ECS/backups/PKI mediante contratos upstream | Validar host/región, productores/bindings, budgets y frescura; no permisos remediadores ni falso Notify real. Backups siguen funcionando sin Sentinel. |
| 6 **Modificar / Añadir** | Simplificar menú CI/CD, luego UI/Archify y migración limpia | Mismo digest/receipts/rollback, controles obligatorios equivalentes, evidencias sanitizadas y prueba de consumidor; no borrar fuentes todavía usadas por generadores. |

No implementar otra plataforma, quorum o registro de permisos. Antes del primer
incremento confirmar los objetivos y retención propuestos; antes de cualquier
prueba cloud obtener su autorización específica. Esta fase entrega **solo este
documento**, sin ejecución AWS, builds, nuevas dependencias ni cambios de contratos.
