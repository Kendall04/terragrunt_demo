# Bootstrap de control ECS — alcance separado del ensayo

Revisión local sobre `1d9dc31471139ad6ed31bdc57deacaf96023dfdc`. Cero llamadas AWS en esta revisión, cero cambios de código, IAM, estado, imágenes o workflows ejecutados. El inventario utilizado es el guardado el 27-oct04:27–04:39UTC, no una nueva observación. Las pruebas cerradas no se repitieron.

## Corrección y recomendación ejecutiva

La ausencia de los tres controladores **no impide usar E16 para preparar/desplegar los cinco roots originales**. `scripts/practical_dev.py:idle()` permite expresamente que no existan. Restaurar el CI/CD protegido sigue dentro del alcance final, pero no es requisito previo de toda preparación del ensayo. Corrige la interpretación anterior de esa ausencia como bloqueo absoluto.

El par de emergencia sí tiene implementación WP4D; los dos pares de infraestructura usan WP5. Sus declaraciones WP2C son inertes hasta una instalación verificada. No equivale a tres proyectos y tres funciones con un Allow genérico: hay paquetes, imágenes, seis roles, permisos y datos protegidos de cada perfil.

Recomiendo preparar primero los planes del modo supervisado existente y reconciliar el estado security antes de autorizar una instalación de control. **No solicitar aún un apply del bootstrap completo:** actualmente no hay plan acotado a esos seis nodos, seis digests de imagen/versiones S3 admitidos ni selección de modo de escritura compatible. No es una petición de ampliar permisos o de levantar SQL para investigar.

## Recursos exactos del bootstrap funcional candidato

Todos los nombres/ARN pertenecen a 341936017254/us-east-1. El nombre del rol lleva siempre `-exec` y cada log group es `/aws/lambda/<función>` o `/aws/codebuild/<proyecto>`.

| Perfil | Lambda gateway | CodeBuild controller | Repositorios ECR propios |
| --- | --- | --- | --- |
| WP5 infra | e1-gateway-infra-dev | e1-controller-infra-dev | e1-wp5-request-gateway-infra-dev; e1-wp5-environment-lifecycle-infra-dev |
| WP5 high-risk | e1-gateway-infra-high-risk-dev | e1-controller-infra-high-risk-dev | e1-wp5-request-gateway-infra-high-risk-dev; e1-wp5-environment-lifecycle-infra-high-risk-dev |
| WP4D emergencia | e1-gateway-emergency-dev | e1-controller-emergency-dev | e1-wp4d-request-gateway-emergency-dev; e1-wp4d-emergency-recovery-emergency-dev |

Las6 instancias compute y esos6 repositorios no aparecieron en los inventarios completos guardados. La existencia/identidad de sus roles y logs NO se comprobó: no asumir que son nuevos ni sustituirlos. Mantener sus RoleId si existen. Las 3 identidades OIDC son `e1-request-infra-dev`, `e1-request-infra-high-risk-dev` y `e1-request-emergency-dev`; el catálogo sigue INERT, commit esperado null y verificación UNVERIFIED. Una autorización de instalación AWS no autoriza configurar GitHub ni inventar ese commit.

Por los 6 nodos, el grafo de código incluye6 declaraciones terraform_data,6 execution roles,6 compute,6 logs,6 repositorios y6 repository policies. Los 2 gateways WP5 tienen cada uno `wp5-protected-lifecycle` y `wp5-exact-controller-package`; los 2 nodos emergencia usan `wp4d-exact`. Los 2 proyectos WP5 usan políticas gestionadas `wp5-infra-dev-0..7` y `wp5-infra-high-risk-dev-0..7` con sus attachments (hasta 16 de cada tipo; fragmentación depende de los bindings reales y debe caber en 6144 bytes). No se añaden boundaries inexistentes por inferencia. Proyección máxima del subgrafo: 74 direcciones más hasta 6 de request roles/policies y cambios de bucket policies/dependencias. **No es número de creaciones ni plan Terraform**: faltan estado security y bindings para saber qué ya existe o cambia. El JSON de evidencia local lista los 6 hashes de contrato candidatos y cada acción de plantilla sin publicar permisos.

Emergencia necesita los tres paquetes/instalaciones mutuamente consistentes: gateway, controller y `cleanup-recovery/cleanup-dev`. La Lambda cleanup existe según inventario; eso no acredita imagen, alias, política, paquete o compatibilidad actual. No se recreará para satisfacer el grafo sin revisar su propietario.

## Buckets y prefijos afectados, sin nuevos buckets por este bootstrap

- `e1-control-bundles-341936017254-us-east-1`: sólo `bundles/sha256/<hash de cada contrato>.json`, VersionId inmutable devuelto por una publicación futura y leído/verificado. Son contratos públicos, sin claves ni contraseñas. Los hashes de catálogo no constituyen instalación aprobada.
- `demo-release-artifacts-341936017254`: WP5 usa `lifecycle/<binding>/current.json` de los 4 bindings infra; WP4D emergencia lee `bindings/deploy-dev.json`, `membership/dev.json`, `eligibility/demo-api/*`, `qualifications/demo-api/*`, `releases/demo-api/by-digest/*`. Preservar versiones/cabezas originales, sin borrar ni sobrescribir incondicionalmente.
- `e1-lifecycle-dev-341936017254-us-east-1`: futuros journals `operations/<binding>/*`, `requests/{infra-dev,infra-high-risk-dev}/*` y los paths de estado/lock enumerados en las plantillas. No conceder sus escrituras como efecto colateral de instalar compute inerte.
- `e1-wp4-dev-341936017254-us-east-1`: gateway emergencia `gateway/dev/emergency/*`, `delivery/dev/*`, `history/*`, `recovery/dev/recovery/emergency/*`; coordinación `arbitration/dev/application.json`, `arbitration/dev/{secrets,shared}.json` y `arbitration/dev/terminals/<binding>/*`. Las actualizaciones condicionales y los propietarios E2 siguen obligatorios.
- Backend del dueño security: bucket/region son entradas externas `E1_SECURITY_STATE_BUCKET`/`E1_SECURITY_STATE_REGION`, key `e1/security/terraform.tfstate` y su `.tflock`. No inferir ese bucket por el nombre de otro proyecto; determinarlo desde el recibo/configuración públicos antes de un plan. Ningún acceso ordinario al state security.

## Part4, backend y privilegios: separar instalación de ejecución

**Para instalar el control con su dueño original security-admin, no hace falta modificar Part4 del operador ni cambiar el backend runtime.** Ese administrador es el propietario previsto por el contrato, no un reemplazo para ejecutar una acción que se le negó al operador. Su instalación necesita aprobación explícita para los recursos/configuraciones del plan; este documento no la concede. Mantener `dev_operator_arn=arn:aws:iam::341936017254:role/TerragruntDemoDevOperator` donde el root admin propaga ese parámetro; omitirlo/default null podría quitar la exclusividad E16 en un apply amplio.

Activar luego WP5 es otra capacidad: sus políticas de 105/118 statements incluyen creación/modificación/retirada de red, ALB/ECS y, high-risk, RunInstances/TerminateInstances del SQL ligado. El gateway puede StartBuild del proyecto exacto. Crear estos permisos sería un cambio material aun sin arrancar builds. No presentarlos como simples lecturas o autorización de plan. Los wildcard de creación/inventario y los recursos exactos futuros deben revisarse antes de instalar las políticas efectivas.

El backend vigente deniega a todo principal excepto TerragruntDemoDevOperator las escrituras en los 5 states DEV. Un Allow de WP5 no lo supera. Hay que elegir un **handoff explícito y exclusivo de modo** para que WP5 sea escritor; no añadir ambos como escritores paralelos ni debilitar el Deny para una prueba. Ese cambio no es necesario para planear con E16 y no se propone ahora.

Las excepciones de Part4v5 para los 4 roles/bucket de portable Sentinel y su nuevo state/lock siguen siendo **otra fase runtime**, no este bootstrap. No cambiar aquí Part4/Part7, boundaries, backup KMS, secretos o políticas históricas. IAM sobre el SQL, SSM, certificado privado y permisos migradores quedan fuera.

## Obstáculos que impiden un apply pequeño ahora

1. `dev_cicd_installation_only=true` selecciona únicamente release/deploy y excluye estos6 nodos; false expone también declaraciones/repositorios de otros perfiles DEV/PROD. No hay selector existente «sólo estos6» que pueda asumirse seguro. Filtrar un for_each en el estado existente puede planear destrucciones ajenas; no usarlo como atajo.
2. Los mapas locales WP4D/WP5 installations/runtime_approvals/environment_bindings están vacíos. Los inputs externos que se usaron históricamente no son prueba de una instalación actual. No rellenarlos con fixture IDs, ni declarar permisos/instalaciones admitidas porque existe un ECR.
3. WP5 exige configuración de capas y recursos reales; WP4D emergencia exige colores, routing y cleanup compatibles. Con runtime vacío no se pueden fabricar esos IDs. Las imágenes/contratos también requieren digests y VersionIds reales verificados. El paquete controller Python cualificado anteriormente para WP4 normal-delivery no prueba las 6 imágenes de este bootstrap.
4. No se ha reconciliado el state security. Un apply de todo el root puede incluir cambios ajenos aunque la intención sea6 compute. Por tanto, no presentar80 como un plan ni autorizar un apply amplio por ese número.

## Coste de control, condicionado y separado de SQL/Fargate

No hay EC2, SQL, red, NAT, ALB ni Fargate en el bootstrap de control. CodeBuild on-demand sólo cobra builds; Lambda sin provisioned concurrency sólo cobra ejecución/requests; no seleccionar fleets reservadas, provisioned concurrency, scans ampliados o servicios extra. ECR y los objetos/logs retenidos sí tienen almacenamiento en reposo.

Una partida **candidata de USD 1 adicional** sólo sería justificable para instalación/readback sin invocar gateways ni StartBuild, con **máximo4 GB totales de imágenes nuevas retenidos 30 días**, contratos S3 hasta 10 MiB y hasta 1000 requests, sin tráfico entre regiones, Actions o registros de ejecución. ECR a USD 0.10/GB-mes = USD 0.40; USD 0.60 queda como margen para requests/almacenamiento pequeño, no tarifa garantizada. Si el artefacto excede4 GB, detener antes de subirlo y recalcular. Esa retención conserva originales/contratos para reversión; después del primer mes persiste coste de almacenamiento si se decide mantenerlos. No prometer tope automático de factura.

No es todavía una solicitud instalable: faltan el plan y las imágenes de esta variante. Si se añaden builds, el coste de BUILD_GENERAL1_SMALL esUSD 0.005/min en el ejemplo oficial de N.Virginia:60 minutos totales serían USD 0.30, **pero no están propuestos/autorizados aquí**, porque esos builds ejecutan un controlador con capacidad de modificar runtime. Las llamadas Lambda requieren su propio presupuesto y admisión de operación; no fingir que una prueba del gateway es un readback inofensivo.

Fuentes oficiales consultadas el 27-oct2026: [CodeBuild](https://aws.amazon.com/codebuild/pricing/), [ECR](https://aws.amazon.com/ecr/pricing/), [Lambda](https://aws.amazon.com/lambda/pricing/), [S3](https://aws.amazon.com/s3/pricing/). No usar free tier ni presupuestos anteriores/EKS. El total del ensayo SQL/Fargate/Sentinel no se deduce de este USD 1.

## Salida reversible y siguiente preparación mínima

Antes de instalar: registrar identidad/generación de cada recurso y versión/documento de cada política; abortar un plan con deletes/replaces de originales, KMS, secretos, shared/PROD/EKS o buckets históricos. Exportar sólo metadata/recibos sanitizados. No instalar triggers, habilitar OIDC, invocar gateways, ejecutar builds, escribir operation/teardown approvals ni mover routing como parte de un readback.

Si se instalara ese bootstrap, su reversión segura inicial sería inhibir invocación/concurrencia, mantener operación/despliegue sin aprobación, restaurar el contenido de trust/policies/config de los recursos preexistentes mediante comparación de concurrencia y conservar imágenes/contratos/state. Las identidades/números de versión nuevos no son reversibles por contenido: no prometer recuperarlos ni eliminar una versión histórica. Este alcance **no autoriza borrar objetos/versiones, imágenes históricas, datos únicos, backups, claves o secretos**, ni ejecutar el teardown amplio EKS/RDS antes rechazado. Cualquier limpieza posterior debe tener su propio plan exacto sin datos ajenos. Mantener compute inerte no genera el cargo horario de una EC2; sí queda el almacenamiento explícitamente reservado.

El siguiente paso mínimo para planes reales no necesita crear estos6 servicios: reconciliar metadata del security backend/control actual; recuperar/validar la configuración de sesión E16 con el operador existente y sus5 states; admitir la preparación de sus planes mediante el owner existente (incluidos locks transitorios exactos si el flujo los requiere), sin apply. Puede generarse un plan real del primer root global; los planes dependientes se sellan con outputs reales de la etapa anterior, no con IDs sintéticos ni un nuevo dueño de state. La fase de red previa y los bindings NAT/SQL se comparan antes de activar nada. La comprobación de identidad fallida anterior sigue inconclusa y no se reintentó en esta revisión.

La credencial migradora, distribución confidencial TLS y transporte SQL admitido no hacen falta para leer configuración o planear red, pero sí para ejecutar y aceptar recuperación estricta hasta Fargate/API. Estos gates permanecen explícitos. La solicitud agrupada del ensayo debe incorporar después sus recursos/deltas/retenciones/retirada y ventana 6–8 h/90 min de cierre; no abrir ahora SQL ni 102/135 recursos para desbloquearlos.
