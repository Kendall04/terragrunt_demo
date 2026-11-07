# Hosting DEMO independiente

Estado: **Free autorizado y rechazado por AWS; alternativa pendiente**. Cuenta `341936017254`,
región `us-east-1`, propietario Kendall. No usa el hosting EKS ni estados del runtime.

## Resultado auténtico del intento Free

El propietario aprobó el template `2cfaad42bf57a86e64d69fd7fa8426a05ee6a8a2e9b72c4a84cc10e575c84952`
y USD 1/mes. Una creación se inició el 7-nov a las 03:05 UTC. PricingPlanManager
rechazó `EG8B1UXYB1WO9` con HTTP400: `The following resources are not eligible for
this subscription tier`. No indicó la propiedad incompatible. No fue AccessDenied
ni una prueba de que Functions/CSP sean incompatibles. Los prerrequisitos de cuenta,
cuotas y template habían pasado; no se afirma una causa más específica sin evidencia.

CloudFormation terminó **ROLLBACK_COMPLETE**: distribución, Functions, WAF, OAC y
suscripción eliminados; solo quedó el bucket nuevo vacío por Retain. Cero uploads,
cero publicación. La distribución estuvo deshabilitada. Coste transitorio modelado
< USD 0,01 por WAF durante unos minutos; facturación atribuible aún no observada.
No se repitió la escritura ni se activó una tarifa alternativa automáticamente.

## Alternativa concreta para aprobación

[`hosting/payg-template.mjs`](hosting/payg-template.mjs), SHA256 generado
`11fd9d4ad78a290a3c0d9e4ed20088484475ed8062e94bdebf3323316c0de3fe`:
los mismos seis recursos de presentación (S3, OAC, bucket policy, distribución,
dos Functions), sin WAF ni suscripción flat-rate. CSP, sandbox, HTTPS, origen privado,
rutas y allowlists son idénticos y están comparados por tests. WAF era un requisito
de Free; sin backend/API, su eliminación no sustituye autenticación ni expone datos.
Se conserva Shield Standard de CloudFront, pero no se afirma rate limiting propio.

Pay-as-you-go explícito: modelo USD 0,10–0,20/mes, misma reserva USD 1/mes con
10.000 solicitudes, 1 GB de salida y <0,1 GB S3; sin asumir franquicias de la cuenta.
Puede superar la reserva si crece el tráfico; no existe límite automático AWS.
No hay cuota mensual fija PRO/BUSINESS. Antes de recrear se retiraría únicamente
el registro del stack fallido y su bucket vacío, verificando cero versiones/delete
markers. Esta alternativa requiere una decisión nueva porque la autorización
anterior condicionaba la publicación a FREE/ACTIVE. No modifica EKS ni el runtime.

## Recursos exactos

Stack CloudFormation `ecs-v2-portfolio-demo`, generado por
[`hosting/template.mjs`](hosting/template.mjs). Ocho recursos:

| Recurso | Configuración |
| --- | --- |
| S3 `ecs-v2-portfolio-341936017254-us-east-1` | Privado, cuatro Block Public Access, owner enforced, SSE-S3, versioning; Retain al retirar stack |
| OAC `ecs-v2-portfolio-oac` | Firma SigV4 siempre |
| Bucket policy | GetObject solo `releases/*`, principal CloudFront y SourceArn de esta distribución; deniega transporte inseguro |
| CloudFront distribution | Un origen S3, dominio HTTPS CloudFront, GET/HEAD, caché administrada, compresión; inicialmente deshabilitada |
| Function `ecs-v2-portfolio-routes` | Allowlist exacta del paquete; reescritura de cinco vistas; 404 real para desconocidas y `/_api` |
| Function `ecs-v2-portfolio-headers` | CSP diferenciada del shell y Archify, HSTS, nosniff, referrer-policy, permissions-policy |
| WAF `ecs-v2-portfolio-free` | Requerido por el plan, exclusivo de ECS; una regla IP 1.000 solicitudes/5 min, sin grupos pagados ni logs |
| PricingPlanManager subscription | `CloudFront / FREE / DEFAULT`, solo esta distribución y este WAF |

Las Functions de CloudFront se publican en su stage `LIVE`; esto es una propiedad
AWS, no el modo de automatización «live» de Impeccable, que no se instala ni ejecuta.

## Plan y coste

Consulta oficial y lecturas de cuenta: 7-nov-2026. Cuenta `PAID / ACTIVE`, cero
suscripciones flat-rate; nombres disponibles. CloudFormation valida el template y
el tipo de recurso Subscription está registrado en la región. Esto acredita
prerrequisitos; **la admisión definitiva requiere Subscription ACTIVE / FREE**.

Se selecciona **Free, USD 0/mes**, con 1 millón de solicitudes y 100 GB mensuales.
Admite OAC, Functions y rate limiting; exige WAF. No admite response-header policies
personalizadas. Las dos CSP se conservan mediante viewer-response Function,
sin reducir el sandbox. No usamos Lambda@Edge, KeyValueStore, dominio propio,
Route53, logs pagados ni origen API.
[Capacidades y límites oficiales](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/flat-rate-pricing-plan.html).

Modelo: tres versiones del paquete (<0,1 GB), 1 GB de salida y 10.000 solicitudes/mes.
CloudFront/Functions/WAF cubiertos por Free; S3 requests y almacenamiento/versiones
no cubiertos por créditos, invalidaciones o servicios fuera del plan pueden generar
cargos. Estimación conservadora **< USD 0,10/mes**, reserva solicitada **USD 1/mes**,
separada del laboratorio. Incluye el breve intervalo pay-as-you-go de creación de
WAF/distribución antes de asociar Free. No es un límite automático AWS. No se añade
ningún plan pagado ni se presupone continuidad ilimitada al exceder cuotas.

Alternativa pay-as-you-go sin WAF: aproximadamente USD 0,10–0,20/mes bajo las mismas
hipótesis y tráfico norteamericano, sin descontar franquicias compartidas; mayor
exposición a coste por tráfico. **No se activa como fallback automático.**
Si Free rechaza requisitos, se detiene la publicación y se retiran solamente los
recursos nuevos vacíos que la autorización permita; no se cambia EKS/runtime.
[Precios CloudFront](https://aws.amazon.com/cloudfront/pricing/pay-as-you-go/),
[S3](https://aws.amazon.com/s3/pricing/).

## Permisos y aislamiento

El administrador existente ejecuta CloudFormation; no se crean roles ni policies
IAM ni credenciales de navegador. Requiere acciones de creación/lectura/actualización
del stack y de sus S3, OAC, Functions, distribución, WAF y suscripción FREE, upload
de objetos y lectura de checksums, y CreateInvalidation sobre la distribución propia.
No necesita `ApprovePaidSubscription`, permisos de API Gateway, ECS, EC2, KMS, SQL
o Sentinel. La bucket policy es el único grant de lectura entre servicios añadido.
Si falta permiso, se informa; no se amplía IAM automáticamente.

El paquete no incluye server/proxy AWS, secretos ni credenciales. DEMO usa memoria.
`connect-src 'none'` bloquea solicitudes API. Archify mantiene sus pins originales,
derivados ya admitidos y iframe opaco (`sandbox=allow-scripts`, sin same-origin).
Su CSP HTTP añade sandbox y permite solo los inline imprescindibles; el shell
no permite inline. Sin catch-all de 403/404 a una página 200. El WAF puede responder
403 antes de las Functions; ese error no contiene documentos ni scripts propios.

## Publicación y rollback

1. Construir dos veces y comparar manifests. Ejecutar pruebas de rutas, CSP,
   aislamiento, doce diagramas, responsive y ausencia de red externa.
2. Generar template, registrar SHA256 y obtener la autorización consolidada.
3. Crear exclusivamente el stack nuevo, `Enabled=false`, `Release=<contentSHA256>`.
   Verificar FREE/ACTIVE; no aprobar otra tarifa. Crear una suscripción Free no
   requiere la operación de aprobación de planes pagados.
   [Contrato CloudFormation](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-pricingplanmanager-subscription.html).
4. Subir únicamente manifest y archivos enumerados a `releases/<SHA>/`, con
   `If-None-Match: *`, SHA256, MIME y cache de 60 s. Nunca sobrescribir una release.
   Leer checksums/versiones de vuelta. Conservar recibo privado.
5. Habilitar la distribución tras verificar objetos, OAC, bucket privado y plan.
   Comprobar HTTPS público, rutas directas, refresh, 404, headers, móvil, DEMO y atlas.
6. Publicaciones futuras: nuevo prefijo verificado, actualización de Release e
   invalidación `/*`. Rollback vuelve al prefijo anterior verificado e invalida.
   Assets tienen nombres estables; durante propagación/caché puede requerirse reload.
   Versiones anteriores se conservan, no hay limpieza automática destructiva.

Retirada propia del hosting: deshabilitar distribución, cancelar Free según estado
real, retirar distribución/functions/WAF/OAC/policy mediante su stack y conservar
el bucket. Borrar versiones/bucket necesita una decisión explícita. La retirada de
EC2/ECS/SQL/NAT del laboratorio no afecta a esta web. No se programa retirada ni se
crean automatizaciones mediante este documento.
