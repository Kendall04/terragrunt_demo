# Auditoría arquitectónica de los diagramas

Alcance: documentación, fuentes de diagramas, generación y controles visuales.
Base de código `5d35edef4f2ee1c0463df483d22745d13cae47cd`; inventario AWS read-only
del 6-nov-2026 a las 23:13:40 UTC. No se ejecutaron planes, pruebas de fallo,
invocaciones, migraciones, lecturas de secretos ni cambios de infraestructura.

## Inventario y disposición individual

| Recurso original | Qué representa y revisión | Hallazgo técnico / visual | Decisión |
| --- | --- | --- | --- |
| `v1-platform` | Plataforma V1 retirada; fuentes `19b1f5e…`; API Gateway/Link/ALB/Fargate/SQL/KMS | Es un mapa histórico coherente. No representa Sentinel, backups horarios ni la configuración TLS/ubicación V2. La vista completa móvil necesita zoom. | Conservar JSON/HTML y hash; sustituir como vista actual mediante `v2-platform`, no reescribir la historia. |
| `v1-network` | Networking V1 con dos NAT Instances/ASG, fuente `19b1f5e…` | No acredita failover cruzado ni SQL HA. Su topología lógica no prueba las subnets/ENI actuales. | Conservar; nuevo `v2-network` con snapshot y ownership E13 explícitos. |
| `az6-recovery` | Ensayo histórico retirado, destino SQL/API previamente preparado; sin ECS/ALB en el camino ensayado | Los 142.630783 s y dos reparaciones pertenecen a ese ensayo, no a recuperación fría V2. Convertirlo en V2 falsificaría el alcance. | Conservar íntegro; `v2-sql-recovery` separa host nuevo, fence y RTO completo. |
| `backup-signals` | Recibos y evaluación local/replay de la etapa anterior | Demuestra contratos locales; no observación Lambda periódica ni entrega actual al inbox. | Conservar; reemplazo explicativo actual en Sentinel/SQL. |
| `future-integrations` | Snapshot del 24-oct, fuente `2c8c3e7…`: piloto AWS sintético retirado y propuesta posterior | Dos correos del piloto no implican instalación del portable actual; diez efectos Pending históricos. No corresponde al conjunto de recursos actual. | Conservar bytes y su relato de propuesta. Nuevo Sentinel completo sin reciclar ese título como presente. |
| `terraform/docs/diagrams/architecture.png` | Raster importado en `9aa2f0f…` (27-ene); mapa general original | La caja de rutas aparece como salto del camino HTTP hacia ALB: una route table no procesa peticiones. Colocación SQL/slots y omisiones son históricas. Sin fuentes editables/procedencia Archify. | Preservar raster como archivo histórico; rotular limitaciones en README local. No presentarlo como V2 ni retocar píxeles sin fuente. |
| `terraform/docs/diagrams/cd-pipelines.png` | Raster de pipelines original, mismo commit de importación | Presenta automatismos/Terragrunt y rollback que no describen CD inhibido y los roots nativos actuales. No prueba el pipeline instalado. | Preservar y clasificar histórico; nuevo `v2-delivery`. |
| Mermaid en `V2-TRUST-AND-THREATS.md` | Mapa de flujos del 5-nov | Omitía SQS entre bus e ingestión y la sonda NAT. La omisión podía sugerir invocación directa. | Corregir únicamente el diagrama y añadir nota fechada; conservar revisión y hallazgos anteriores. |
| Mermaid de ownership E15 / otros runbooks | Dependencias/órdenes de ejecución, no paquetes de red ni inventario AWS | Su semántica es útil en contexto histórico; E16 está retirado. | No convertir grafos de dependencia en topología. Enlazar procedimiento nativo actual. |
| Explorer SVG propio y capturas en `portfolio/` | Representación explicativa local y cinco iframes históricos | No son una sexta salida Archify ni evidencia adicional de instalación. El índice dice que la vista conjunta V2 estaba pendiente. | Auditado como consumidor; no modificar UI, catálogo, CSS ni pins. V2 vive en documentación separada. |

Los cinco hashes HTML se conservan en `portfolio/archify-pins.json`; los hashes
JSON y revisiones particulares siguen en `GENERATION.json`. Las dos PNG se
registran en la evidencia V2 sin atribuirles un generador desconocido. La prueba
automática impide sustituir silenciosamente los originales.

**Diferencia de procedencia comprobada:** el quinto recibo conserva el SHA del
JSON con CRLF (`e3a320c8…`), mientras Git contiene exactamente el mismo texto LF
(`a1e4a294…`). La conversión determinista LF→CRLF reproduce el hash del recibo.
No es un cambio de grafo ni se corrigió cambiando el pin: se conserva el registro
y la prueba trata explícitamente esa única diferencia de fin de línea.

## Matriz de discrepancias y fuentes verificables

Los paths son relativos al repositorio; los enlaces de nodo del HTML fijan líneas
y commit. `TRACEABILITY-V2.json` enumera también **todas** las relaciones y sus
referencias. Esta matriz explica la inferencia que una lista de hashes no puede probar.

| Relación / afirmación auditada | Contraste verificable | Representación resultante |
| --- | --- | --- |
| Cliente → Gateway → Link → ALB → Fargate | `target/dev/edge/modules/apigateway/apigw_http.tf:25–63`; `edge/modules/vpc_link/vpc_link.tf`; `global/modules/alb/alb.tf:18–33`; reglas SG en `global/ordinary-security_rules.tf`; snapshot API/routes/stage | HTTPS externo; HTTP :8080 privado. Route table no es un proxy de entrada. |
| API pública sin autenticación | Snapshot `routesApi[].AuthorizationType=NONE`, cuatro rutas; `V2-TRUST-AND-THREATS.md` revisión de exposición | Límite visible, no un icono de candado genérico de extremo a extremo. |
| AZ y colocación | Snapshot EC2/subnets/ASG, readback de recuperación `V2-RECOVERY-SECURITY-20261105.md:282–324` | Privada A = sonda; SQL y blue actuales en B. ALB/Link se extienden a ambas privadas. Elegibilidad de subnets no equivale a distribución de tareas. |
| Ruta privada → NAT de su zona | `global/modules/vpc/route_tables.tf:32–49` solo declara tablas/asociaciones; `scripts/recovery/nat.py:65–95` y `scripts/wp4d/nat_resolver.py:59–90` seleccionan ENI/miembro; snapshot rutas | E13 mantiene el default privado. ASG repone EC2 desde LT :4; handlers :6 reparan EIP/ruta/SDC. No NAT Gateway ni failover cruzado automático. |
| ECS → KMS y SQL | `Services/IEncryptionService.cs:30–51`; `Data/DatabaseSecurityPolicy.cs`; `Data/RuntimeDatabasePermissions.cs`; `V2-RECOVERY-SECURITY-20261105.md` pruebas POST/GET | Cifrado de texto vía task role; SQL TLS con hostname/trust; no migración al arrancar HTTP. |
| Execution role ≠ task role ≠ usuario SQL | `apps/modules/ecs_service/taskdef.tf`; tabla de identidades y readbacks de handoff en los registros de seguridad/recuperación | Execution pull/logs/secreto al inicio; task KMS; runtime SELECT/INSERT + metadata EF. Host admin y migrador separado no son permisos runtime. |
| Productor → S3 | `operations/sql-backup/sql-backup.timer.in`; `recovery/install_native_backup.py`; `recovery/NATIVE-RECOVERY.md:48–52,86–100`; evidencia de timer real | Horario persistente, COPY_ONLY/CHECKSUM y subida versionada. El observador externo no ejecuta un restore ni CHECKDB. |
| Backup → Lifecycle | `portable/backup_retention.py:33–130`; snapshot tres reglas `dev-v2-20261106-*`; registro Sentinel §Remote backup retention | 7 días para objetos elegibles, +1 día no actuales; últimos dos pares sin tag. Preservar prefijos ajenos no significa que todos los prefijos históricos carezcan de sus propias reglas antiguas. |
| Restauración ↔ retención | `backup_retention.py:1–6,60–65`; `NATIVE-RECOVERY.md:48–100` | Pin independiente exigido fuera TTL, marcado NO VALIDADO para copia automatizada/ensayo con Lifecycle. No afirmar atomicidad ni Object Lock. |
| Fence → nueva EC2 → restore → activación | `NATIVE-RECOVERY.md:42–100`; `native_host.py`; recibos CROSS/SAME-AZ del informe de recuperación | Drain, logins OFF, READ_ONLY, backup final, sustitución revisada, source terminated comprobado, CHECKDB/hash/EF y handoff. Discos cifrados conservados; recuperación supervisada. |
| Observador → bus → SQS → ingestión → DDB | `storage_observer.py:128–148`, `nat_observer.py:79–99`, `trial/runtime/main.tf:97–133,192–197` | Cola reports explícita; batch 5 y fallos parciales. DLQ reports distinta de DLQ operations. No bus→Lambda directo. |
| Observador NAT ↔ sonda | `nat_observer.py:8–99`; `nat_probe.py:19–67`; `trial/nat-observer.tf:74–115` | Lecturas ASG/EC2/EIP/ruta/SDC y prueba HTTPS son señales distintas; sonda privada A, plazo total 6 s. Error del ejecutor/throttling = Unknown. |
| Worker ↔ journal | `Ecs.Backup.Portable.Host/Function.cs:30–64`, `CurrentBacklog.cs`, integración portable fijada; runtime/main.tf schedules | 64 requests/cuatro jobs por admisión, dos admisiones serializadas/minuto, concurrency 1; checkpoint/CAS/deduplicación. No sumar compensaciones como si se borraran fallos. |
| Watchdog y cleanup | `Function.cs:49–64`, `CurrentBacklog.cs`, `ArchiveCompensation.cs`; runtime schedules | Dos funciones distintas. Watchdog separa salud actual y deuda histórica; cleanup no se presenta como reset de journal. |
| Worker → archivo/SNS → inbox | `trial/runtime/main.tf:146–167`; `security.tf:49–96`; código de notice; IDs/timestamps del ensayo | SSE-KMS por servicio y recurso; SNS ACK ≠ inbox. Cuatro correos anteriores verificados externamente por ChatGPT/Gmail, quinto del tercer NAT acreditado en registro, no reenviados aquí. |
| CloudWatch → SNS | `runtime/main.tf` alarmas Health/errores/DLQ | Aviso operativo de CloudWatch separado del aviso de dominio/incident de Sentinel. La alarma Health del primer ensayo no acredita detección NAT. |
| NAT detectado → recuperado | `SENTINEL-CHAOS-20261106.md:131–185` | Timeline conserva Unknown, resolución y correo, sin inventar un correo de escalación. 2m29.191s es cota desde despacho hasta primera confirmación HTTPS; no duración física exacta del corte. |
| Terraform ↔ deployment | `ecs_service/service.tf:33–38`; `alb/alb.tf:28–32`; `native-dev-lifecycle.md`; `V2-TRUST-AND-THREATS.md` ownership | Skeleton/ownership separados de revisión, desired count y forwarding nativos. Ignorar estos campos es deliberado, no drift autorizado sin límites. |
| GitHub/OIDC/WP3/WP4 | `.github/workflows/ci.yml`, `cd.yml`; registro DEV y contrato de entrega | CI activo; CD/gateways inhibidos según evidencia. Artefactos publicados ≠ instalados ≠ qualification. V1 A→B→A no se acredita como nuevo rollback V2. |

El prefijo abreviado `target/dev/` en la tabla corresponde a
`terraform/modules/target/dev/`; `portable/` a `operations/integrations/portable/`.

## Hallazgos conservados, no corregidos operativamente

1. API sin autenticación, HTTP interno y leaf TLS de demo: visibles en confianza.
2. Un SQL y una tarea blue: recuperación fría, no servicio multizona redundante.
3. Imagen de aplicación cualificada no sanea los hallazgos de imágenes históricas
   de control-plane; véase el informe de seguridad. No se reescaneó ni desplegó nada.
4. No PITR, no Object Lock, eliminación Lifecycle asíncrona, pin de restore por
   verificar; los permisos administrativos siguen siendo un límite de confianza.
5. La sonda de A no demuestra B ni disponibilidad de toda la API. Eventos EC2 y
   salud ASG tampoco sustituyen HTTPS real.
6. Los cuatro fallos y compensaciones del journal son evidencia preservada. La
   DLQ histórica no se purgó ni se leyó mediante ReceiveMessage en esta auditoría.
7. Se mantienen separados 6h56m59.934s saludables anteriores al cambio y
   23m59.625s posteriores documentados en PR #34. No se suman como 24 h continuas
   ni se atribuye al snapshot de reglas una prueba nueva de estabilidad.

## Revisión cruzada final

Todas las vistas usan el mismo corte temporal y vocabulario. Plataforma omite
intencionadamente el detalle de subnets y journal; red/Sentinel lo expanden.
Confianza expresa autoridad, no un segundo plano de paquetes. Recuperación SQL
representa orden operativo y estados, no una réplica activa. El incidente muestra
hechos fechados; su resultado no modifica el contrato de todos los fallos futuros.
La matriz, el inventario saneado, los fragmentos fijados y las capturas permiten
revisar estas decisiones sin acceso a evidencia privada o credenciales.
