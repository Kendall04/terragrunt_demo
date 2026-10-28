# Siguiente ensayo nativo de ECS: alcance actualizado y límites

**Checkpoint histórico, supersedido en la siguiente admisión:** solicitar primero
el [plan E16 de red, sin despliegue](PLAN-ONLY-E16.md). La seguridad/retirada portable
ya está implementada localmente y el inventario mock vigente es 69, descrito en
[README](README.md). La propuesta de empezar desplegando portable y sus importes
inferiores no son autorización ni el camino crítico actual.

Preparación local desde956c38a,26-oct-2026. No autorización de gasto, acceso, publicación,
instalación ni creación. No preflight privado AWS esta noche. Los ensayos anteriores
están cerrados; USD6/102 no son presupuesto ni inventario vigentes.

## Recomendación concreta y secuencia

1. Primero admitir el perfil portable aislado **62 recursos** para probar en AWS la
   nueva ingesta/estado/ACK/outbox/avisos y salud del worker, con eventos SINTÉTICOS.
   Es el alcance pequeño que puede ejecutarse sin repetir RunCommand. Propongo
   **USD2 nuevos** sólo para este backend: objetivo2h, detener actividad diagnóstica
   a4h, reservar90min para retirada, máximo absoluto24h incluyendo limpieza. El
   consentimiento, los permisos actuales y el plan real siguen pendientes; nada se
   deja activo esta noche. Una nueva suscripción debe confirmarse nativamente.
2. El cohost se probará en el SQL privado del siguiente ciclo SQL/ECS admitido, sin
   otra EC2 observadora. Ahora su paquete/bootstrap/publicador está calificado LOCAL;
   no existe un SQL live asumido/reutilizable. Antes hay que reconciliar lo borrado
   por el dueño, vincular AMI/OS/rol y la fuente de backup real. La observación de
   manifiestos/telemetría arranca autónoma; el productor espera el handoff real de
   credenciales. Si no hay manifiesto válido, emitir UNKNOWN, nunca fabricar HEALTHY.
3. Fencing/restore/CHECKDB y servicio público Fargate requieren su transporte admitido
   y prueba propia. El rechazo histórico SSM sigue sin causa demostrada; no se hará
   retry ni se elegirá SSH/documento/principal alternativo para eludirlo. El resultado
   de1 no es una recuperación de ECS ni una prueba nativa del productor/observador.

No se presenta el ciclo grande como instalable ni se pide un nuevo permiso ahora.
El alcance1 cierra un conjunto útil de aceptación nativa y deja esos otros límites
explícitos; no exige EC2/SQL/NAT mientras se valida el runtime portable.

## Inventario y propiedad

Los62 son el plan con proveedor SIMULADO6.28, no inventario AWS ni plan aplicado:
tabla1; bucket/configuración5; IAM12 (4 roles,4 boundaries,4 inline); Lambda15;
colas/políticas5; EventBridge9; logs/métrica/alarmas12; SNS3.
Artefactos implícitos: versiones Lambda/S3, streams/logs, filas/recibos/índices/PITR,
estado terminal y generaciones nativas que deben inventariarse y retirarse.
No CloudFormation, nuevo servicio de negocio, PKI o segunda SQL permanente.

Para el proyecto completo, los otros TARGET actuales suman73 direcciones propuestas
(global49,data5,platform1,apps9,edge9). Sustituir el bloque Sentinel antiguo29 por62
da un **candidato aritmético135**, NO un plan integrado ni recursos nuevos ya admitidos.
El flujo práctico materializa los TARGET originales (`scripts/practical_dev.py:216-243`);
el portable está preparado como root aislado, sin selección integrada demostrada en
ese flujo. El opt-in de la nueva unidad/selector debe revisarse e instalarse con
autoridad nueva antes del ensayo conjunto. No aplicar ambos a los mismos nombres ni cambiar gestores por recurso.
No cotizar ni desplegar135 con USD2, ni reciclar USD6. Su coste y retirada se sellarán
con el plan real y el transporte SQL viable; no inventar una cifra para desbloquearlo.

El backend portable tiene una única unidad Terraform/Terragrunt y root aislado;
conserva5.100 para el resto,6.27 histórico y el lock upstream6.70; sólo el root nuevo
usa6.28 verificado. Estado propuesto y detalles de62 en
[propuesta completa](NATIVE-TRIAL-PROPOSAL.md). El selector vigente no es aprobación.

## Accesos a agrupar antes de crear

-Administrador existente: preparación/reversión de los deltas exactos del operador
 y excepción limitada de backend. Sin nuevas credenciales. Primero leer políticas,
 hashes/versiones/cuotas/concurrencia y denegaciones vigentes; hoy sólo hay snapshots.
-TerragruntDemoDevOperator: lifecycle crear/leer/actualizar/borrar de las62 direcciones,
 publicar el ZIP exacto a las cuatro Lambdas, PassRole sólo a sus cuatro roles, prueba
 sintética PutEvents sólo al bus/fuente/tipo del candidato y retirada de datos propios.
 El límite de20 cuenta ENTRADAS/intentos, no20 lotes. Registrar/debitar antes de enviar;
 nunca ejecutar el publicador EC2 con credenciales del portátil fingiendo otra identidad.
 El transporte del ensayo backend es una acción sintética distinta que requiere permiso
 explícito propio; no ejecuta ni sustituye el comando SSM rechazado.
-Cuatro roles de runtime y boundaries ya propuestos: sólo tabla/índices, colas/logs,
 archivo propio y SNS específico según función; cero EC2/SSM/IAM/secretos/KMS/NAT.
 Editar sus políticas/boundaries permite modificar su contenido: el nombre no impone
 por sí solo un límite. Get/DeleteEventSourceMapping Resource* puede afectar metadatos/
 mappings regionales: explicitar alcance efectivo, expiry, uso sólo de su UUID y reversión.
-Cohost futuro: demo-dev-data-sql-ec2-role con PutEvents sólo al bus
 ecs-portable-r20261026p1, fuente sentinel.report.sql-observer y detail-type
 Sentinel Observation v1, us-east-1 y ventana admitida. Lectura/versionado y KMS sólo
 del nuevo tar publicado, sin nuevos BAK ni ampliar retención. VersionId aún desconocido.
 Retirar sólo una propia excepción SQS temporal si realmente existe, no otros permisos.

En el preflight permitido posterior se deben resolver cuenta341936017254/us-east-1,
identidad efectiva, nombres libres, políticas compartidas/slots históricos, backend,
encriptación y manual deletions. Si hacen falta Part4/7/KMS o pérdida de metadata de
versiones, añadir diff/hash/reversión al único paquete. No asumirlos permitidos.

## Probes y límites de aviso

Instalar disabled; confirmar SNS nativamente; admitir y activar runtime/mapping sólo
después. Publicar hasta20 entradas/intentos sintéticos, IDs estables y3 intentos por
pendiente. Un episodio de atención y una recuperación,3 intentos durables por aviso;
SNS puede duplicar. Persistir/releer recibo/auditoría/estado/archivo y clasificar ACK,
duplicados, errores parciales, DLQ y trabajo futuro/incierto. No llamar outbox drenado
a un estado con supervisión futura o efectos no soportados. No inferir inbox de MessageId.

Dos expectativas: backup Artifact/frescura2h y telemetría Reported/frescura20min, parámetros
experimentales que no son RPO/RTO final. Heartbeat no renueva dataAt del backup. Para el
piloto sintético, conservar telemetría fresca dentro del presupuesto mientras se prueba
el episodio de backup, evitando un segundo episodio accidental. La pérdida/regreso de
host real queda para el cohost admitido, con datos y presupuesto propios.

Watchdog portable: lee el registro operativo del worker y emite SentinelHealth en logs;
el metric filter/alarma es la vía operativa separada. No usa el DurableWatchdog con avisos
persistidos en esta composición. Para probarlo: detener sólo el schedule worker propio,
leer HEARTBEAT_MISSING/UNKNOWN, reanudar y observar recuperación; no reparar NAT/SQL.
Las siete acciones de alarma permanecen OFF en el piloto de dos avisos. Su entrega
operativa por correo es un probe futuro explícito, no cubierto por el aviso de backup.

Avisar al dueño cuando la parte nativa admitida esté lista y reservar30min para verla,
dentro del gasto/retirada. En1 sería consola/evidencia/email, NO la web ECS desplegada.
La ventana de API pública/diagramas corresponde al ensayo completo. Si no responde,
terminar/retirar sin dejar infra indefinida. Diagrama conjunto final sólo después E2E.

## Coste del alcance1 y retirada

La estimación serverless previamente cotejada con tarifas oficiales usa32.700GB-s
(3 schedules/min,512MiB,60s durante330min más100 invocaciones de ingesta) ≈USD0,545
aUSD0,0000166667/GB-s; requests <USD0,001. Reservas: Dynamo/PITR0,40; logs/alarmas0,15;
mensajería0,10; S3/backend primer mes0,10; contingencia0,704. Total propuesto USD2,
sin free tier ni garantía de tope automático. Límites de volumen y abortos en la propuesta
completa. No se ejecuta un nuevo cotejo privado ni factura aquí.
[Lambda](https://aws.amazon.com/lambda/pricing/),
[EventBridge](https://aws.amazon.com/eventbridge/pricing/),
[SQS](https://aws.amazon.com/sqs/pricing/). Las otras cifras son reservas, no tarifas unitarias.

Retirada preparada como secuencia, pendiente de IDs/plan real: desactivar publicación,
schedules, mapping y alarmas; exportar y clasificar efectos/recibos/DLQ; quitar protección
sólo de la tabla propia; purgar objetos/versiones/delete markers; saved destroy propio;
verificar funciones/versiones/aliases/mapping, targets/bus, colas, SNS, logs, tabla/PITR,
bucket, roles/boundaries. Revertir exactamente IAM/backend con concurrencia y conservar
estado terminal/evidencia. Ningún bootstrap temporal debe quedar por una tarea local.
Ninguna operación AWS de retirada se ejecuta desde este documento.
Datos nuevos sintéticos se retiran tras exportar; originales y backups2+2d intactos.
En el futuro ciclo grande: NAT propio primero y espera/reconciliación nativa; no
DisassociateAddress retry, DeleteVolume suelto, hacks de estado o borrado ajeno/EKS.
