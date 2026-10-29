# Admisión mínima del primer plan E16

> **Histórico, 28-oct-2026:** E16 está retirado. Este contrato y sus autorizaciones
> no son el camino operativo actual. Usar el [procedimiento DEV nativo](../../../terraform/docs/native-dev-lifecycle.md)
> con un nuevo plan, el mismo operador y estados originales, locking y permisos
> de retirada verificados; apply requiere autorización separada. El plan E16
> anterior se conserva como evidencia y no se aplicará.

Solicitud preparada; **ninguna autorización AWS nueva queda ejecutada por este
documento**. Evidencia previa conservada en `logs/certification-20261027`;
su E16 histórico de 43 creaciones no es un plan vigente. La preparación portable
actual está en [README](README.md). No hace falta instalar los controladores
CI/CD ausentes para `dev init` / `dev bootstrap-network-plan`: el procedimiento
E16 admite ausencia demostrada por ListFunctions/ListProjects, nunca AccessDenied.

## PLAN-ONLY

- Cuenta `341936017254`, región `us-east-1`, workspace `default`, una sesión humana
  secuencial, máximo **3600 segundos**, un plan guardado de **global network-only**.
  Antes de asumir el rol, el dueño debe fijar `starts_at` y `expires_at` UTC en el
  recibo aprobado (diferencia máxima 1h); no hay fechas ni aprobación implícitas.
- Principal legítimo: `arn:aws:iam::341936017254:role/TerragruntDemoDevOperator`.
  La evidencia del 28-oct muestra trust del usuario `cnp-cert-admin`, sesión máxima
  3600s y transferencia exclusiva del backend ya instalada. El perfil
  `cnp-cert-dev` por sí solo resuelve ese usuario: verificar con STS que la sesión
  efectiva sea `arn:aws:sts::341936017254:assumed-role/TerragruntDemoDevOperator/...`.
  Solicitar uso explícito de esa ruta E16; no cambiar de principal ante un rechazo.
- Backend existente: `arn:aws:s3:::e1-lifecycle-dev-341936017254-us-east-1`.
  Autorizar lectura **interna** por Terraform (`s3:GetObject`) de estas cinco keys:

  ```text
  e1/lifecycle/dev/global/terraform.tfstate
  e1/lifecycle/dev/data/terraform.tfstate
  e1/lifecycle/dev/platform/terraform.tfstate
  e1/lifecycle/dev/apps/terraform.tfstate
  e1/lifecycle/dev/edge/terraform.tfstate
  ```

  Permitir `s3:ListBucket` sólo con `s3:prefix` igual a esas cinco keys y sus
  respectivos sufijos `/workspaces` (incluido `/workspaces/` si lo solicita el
  cliente); Terraform verifica workspace default. Metadatos del bucket necesarios:
  `s3:GetBucketLocation`, `GetBucketVersioning`, `GetBucketPublicAccessBlock`,
  `GetEncryptionConfiguration`, `GetBucketPolicy`. No acceso al state security,
  shared, secrets ni a las keys futuras de Sentinel.
- Única escritura/eliminación admitida: `s3:GetObject`, `PutObject`, `DeleteObject`
  sobre `arn:aws:s3:::e1-lifecycle-dev-341936017254-us-east-1/e1/lifecycle/dev/global/terraform.tfstate.tflock`.
  Es el lock nativo transitorio del plan global. Los otros cuatro locks no son
  necesarios para este primer plan. Prohibir PutObject/DeleteObject de los states,
  DeleteObjectVersion, migración/init de un backend nuevo, force-unlock y
  `-lock=false`. Si init necesita escribir state o otro lock, detener y conservar
  la evidencia; no ampliar permiso automáticamente.
- Mantener los Deny existentes: TLS, aislamiento DEV, escritor exclusivo,
  retención de state y prohibición de administrar backend. Los Allows E16 ya
  inventariados no necesitan reemplazar versiones IAM. Si se emite sesión
  restringida, intersectarla con permisos instalados y fecha/región exactas;
  permitir sólo lecturas y el lock anterior. La expiración de Allows no neutraliza
  permisos heredados amplios: imponer también el límite de sesión y la exclusión
  de mutaciones, sin retirar los Deny instalados.
- Lecturas auxiliares ya contempladas por E16: `s3:GetObject` de
  `arn:aws:s3:::e1-wp4-dev-341936017254-us-east-1/arbitration/dev/application.json`
  (E2 RELEASED); `lambda:ListFunctions`, `lambda:GetFunctionConcurrency` sólo para
  `e1-gateway-infra-dev` / `e1-gateway-infra-high-risk-dev` si existen;
  `codebuild:ListProjects`, `ListBuildsForProject`, `BatchGetBuilds` sólo para los
  proyectos existentes `e1-controller-{infra-dev,infra-high-risk-dev,deploy-dev,emergency-dev}`.
  ListFunctions/ListProjects requieren `Resource="*"`; no se invoca función ni build.
  `autoscaling:DescribeAutoScalingGroups` verifica ausencia de `demo-dev-asg-nat-a/b`;
  `ec2:DescribeAvailabilityZones` resuelve AZ. El refresh del state usa los
  Describe/Get existentes de los recursos DEV allí registrados y `tag:GetResources`
  si hay filas con tags; no se concede escritura de infraestructura. Un recurso
  ajeno, error de lectura o estado parcial exige conciliación antes de continuar.
- Directorio privado **externo al repositorio**, preparado vacío y con ACL verificada:
  `C:\Users\PC\.codex\visualizations\2026\10\28\01a1805e-670d-79b3-bb52-5f59353e6aee\e16-private`.
  Dueño PC, DACL protegida, sólo PC y SYSTEM con herencia a hijos, dos ACE Allow.
  Usar hijo nuevo `session-01`, todavía inexistente, porque `init` rechaza adoptar
  directorios existentes. Verificar ACL nuevamente bajo el mismo usuario antes de
  escribir; conservar allí binario, previews y metadatos privados. No copiar
  credenciales ni emitir state/plan JSON al informe. Publicar sólo resumen saneado.

Tras aprobación de **este** alcance: comprobar STS, SHA final/checkout limpio,
Terraform **1.13.4** y locks originales E16 (AWS **5.100.0**, no el 6.28 portable).
Config externo `E16_SUPERVISED_DEV_V1` con SHA aprobado, cuenta/región/rol anteriores
y referencias protegidas existentes; `protected_nat_launch={}` sólo por el modo
network-only. Usar la ruta Windows nativa existente, sin WSL ni credenciales en la VM:

```text
python -I -B scripts/original_dev.py dev init --config <private-config.json> --directory <private-root>/session-01
python -I -B scripts/original_dev.py dev bootstrap-network-plan --config <private-config.json> --directory <private-root>/session-01
```

No ejecutar `apply`, `down-plan`, `destroy`, SSM, CD ni instalación IAM/KMS. No
leer valores de secretos. Al terminar, comprobar liberación normal del lock,
conservar evidencia privada y cerrar la sesión temporal. Un lock residual se
investiga con su dueño; nunca se borra para eludir concurrencia.

## APPLY y certificación posteriores: autorización separada

1. Revisar el plan global real, presupuesto/ventana nuevos y permisos de retirada
   (incluidos VPC en DetachInternetGateway y subnet en DisassociateRouteTable).
   Autorizar su apply sólo después. No reutilizar el presupuesto histórico USD12.
2. Con outputs **reales** de global: VPC, subnets, SG NAT/SQL/aplicación/VPC Link,
   EIP/rutas, listener y target groups. Security owner renueva versiones de ambos
   launch templates NAT y bindings E13/controlador; después plan global NAT.
   No inventar IDs o versiones hoy.
3. Planes data → platform → apps → edge con outputs previos. Migrador separado,
   secreto migrador fuera de state, TLS SQL `sql.demo.internal` con distribución
   privada y confianza Linux, validación real SqlClient, migraciones separadas y
   fencing de único escritor. El acceso SSM admitido se decide por separado;
   no repetir diagnósticos denegados ni atribuirlos al acceso SQL histórico.
4. Sentinel aislado: backend/lock nuevo explícito, dos CMK externas diferentes y
   sus políticas exactas, bucket dedicado de logs, permisos lifecycle/PassRole
   propios, paquete y configuración vinculados, destinatario SNS confirmado.
   No modificar las versiones históricas IAM ni los recursos EKS. Instalar
   CI/CD/OIDC y bindings protegidos sólo para las fases que los necesitan.
5. Admitir ensayo y retirada propios, manifiesto/lotes S3, estados retenidos y
   reversión de permisos temporales. Mantener ≥90min para retirada dentro de la
   ventana aprobada; Sentinel observa 75min con **20 entradas totales incluyendo
   reintentos**, no ocho horas continuas. No restaura SQL ni repara NAT.
