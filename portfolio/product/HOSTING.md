# Hosting DEMO independiente

Current collection: five ECS views plus twelve historical snapshots, including
Sentinel. [Current atlas](../../docs/interactive/CURRENT-INDEX.md) and
[separation record](../../docs/history/SENTINEL-SEPARATION.md) define the scope.
The public DEMO remains independent of runtime, SQL and monitoring.


Estado: **PUBLICADO y verificado por HTTPS — 7-nov-2026**. Cuenta `341936017254`,
región `us-east-1`, propietario Kendall. No usa el hosting EKS ni estados del runtime.

**[Abrir Cloud Resilience Laboratory](https://d20ioz705caon7.cloudfront.net/)**.
Distribución `E1PKEWJYYS672Q`, stack `ecs-v2-portfolio-demo`, UPDATE_COMPLETE;
CloudFront Deployed/Enabled. [Readback AWS](evidence/public/HOSTING-READBACK.json)
y [Chrome HTTPS](evidence/public/PUBLIC-HTTPS-QA.json): PASS. 48 objetos versionados
verificados (47 archivos + manifest), cinco vistas, doce diagramas, DEMO/reset,
rutas directas/refresh, 404, MIME, CSP, desktop/móvil; cero llamadas al backend.

Release inmutable:
`3ede367cc3a7e4d48c8fa1d0fc2f66ef75be9ebf8e34d74299d86d9dda6b9b21`.
Reserva independiente USD 1/mes. Facturación atribuible aún no disponible; no se
presenta el modelo como gasto observado ni como límite automático.

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

## Alternativa expresamente aprobada

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
No hay cuota mensual fija PRO/BUSINESS. El propietario aprobó expresamente esta
alternativa y la misma reserva USD 1/mes. Se retiraron únicamente el registro del
stack fallido y su bucket vacío, verificando cero versiones/delete markers.
La autorización original condicionaba la publicación a FREE/ACTIVE; no se hizo
fallback hasta recibir la nueva decisión. No modifica EKS ni el runtime.

## Recursos exactos

Stack CloudFormation `ecs-v2-portfolio-demo`, generado por
[`hosting/payg-template.mjs`](hosting/payg-template.mjs). Seis recursos:

| Recurso | Configuración |
| --- | --- |
| S3 `ecs-v2-portfolio-341936017254-us-east-1` | Privado, cuatro Block Public Access, owner enforced, SSE-S3, versioning; Retain al retirar stack |
| OAC `ecs-v2-portfolio-oac` | Firma SigV4 siempre |
| Bucket policy | GetObject solo `releases/*`, principal CloudFront y SourceArn de esta distribución; deniega transporte inseguro |
| CloudFront distribution | Un origen S3, dominio HTTPS CloudFront, GET/HEAD, caché administrada, compresión; inicialmente deshabilitada |
| Function `ecs-v2-portfolio-routes` | Allowlist exacta del paquete; reescritura de cinco vistas; 404 real para desconocidas y `/_api` |
| Function `ecs-v2-portfolio-headers` | CSP diferenciada del shell y Archify, HSTS, nosniff, referrer-policy, permissions-policy |

El generador Free original conserva los dos recursos rechazados como evidencia
de la propuesta revisada; no están en la instalación pay-as-you-go.

Las Functions de CloudFront se publican en su stage `LIVE`; esto es una propiedad
AWS, no el modo de automatización «live» de Impeccable, que no se instala ni ejecuta.

## Comparación de planes y coste

Consulta oficial y lecturas de cuenta: 7-nov-2026. Cuenta `PAID / ACTIVE`, cero
suscripciones flat-rate; nombres disponibles. CloudFormation validó el template y
el tipo de recurso Subscription estaba registrado en la región. Esos prerrequisitos
no acreditaban admisión: AWS rechazó efectivamente la suscripción Free.

Se evaluó **Free, USD 0/mes**, con 1 millón de solicitudes y 100 GB mensuales.
Admite OAC, Functions y rate limiting; exige WAF. No admite response-header policies
personalizadas. Las dos CSP se conservan mediante viewer-response Function,
sin reducir el sandbox. No usamos Lambda@Edge, KeyValueStore, dominio propio,
Route53, logs pagados ni origen API.
[Capacidades y límites oficiales](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/flat-rate-pricing-plan.html).

Modelo: tres versiones del paquete (<0,1 GB), 1 GB de salida y 10.000 solicitudes/mes.
La propuesta Free modelaba **< USD 0,10/mes** y reserva **USD 1/mes** separada del
laboratorio. El coste transitorio del intento fallido no equivale a facturación
observada. No se contrató un plan fijo PRO/BUSINESS.

Plan elegido tras aprobación, pay-as-you-go sin WAF: **USD 0,10–0,20/mes** bajo las mismas
hipótesis y tráfico norteamericano, sin descontar franquicias compartidas; mayor
exposición a coste por tráfico. Reserva aprobada **USD 1/mes**, sin límite automático
AWS. Requests S3, almacenamiento/versiones, transferencia, Functions e invalidaciones
fuera de franquicia pueden generar cargos. Revisar consumo antes de promocionar
a una audiencia mayor. No se activó como fallback automático ni se cambió EKS/runtime.
[Precios CloudFront](https://aws.amazon.com/cloudfront/pricing/pay-as-you-go/),
[S3](https://aws.amazon.com/s3/pricing/).

## Permisos y aislamiento

El administrador existente ejecuta CloudFormation; no se crean roles ni policies
IAM ni credenciales de navegador. Requiere acciones de creación/lectura/actualización
del stack y de sus S3, OAC, Functions y distribución, upload
de objetos y lectura de checksums, y CreateInvalidation sobre la distribución propia.
No necesita PricingPlanManager, WAF, `ApprovePaidSubscription`, API Gateway, ECS, EC2, KMS, SQL
o Sentinel. La bucket policy es el único grant de lectura entre servicios añadido.
Si falta permiso, se informa; no se amplía IAM automáticamente.

El paquete no incluye server/proxy AWS, secretos ni credenciales. DEMO usa memoria.
`connect-src 'none'` bloquea solicitudes API. Archify mantiene sus pins originales,
derivados ya admitidos y iframe opaco (`sandbox=allow-scripts`, sin same-origin).
Su CSP HTTP añade sandbox y permite solo los inline imprescindibles; el shell
no permite inline. Sin catch-all de 403/404 a una página 200. No hay WAF propio ni
rate limiting del proyecto; no se presenta CloudFront como autenticación.

Se verifican por AWS API template instalado, OAC, bucket policy, BPA, ownership,
cifrado, versioning, Functions efectivas y asociaciones. Cada objeto se lee con
ChecksumMode=ENABLED. No basta con CREATE_COMPLETE.

## Publicación y rollback

1. Construir dos veces y comparar manifests. Ejecutar pruebas de rutas, CSP,
   aislamiento, doce diagramas, responsive y ausencia de red externa.
2. Generar template pay-as-you-go, registrar SHA256 y comprobar la aprobación.
3. Crear exclusivamente el stack nuevo, `Enabled=false`, `Release=<contentSHA256>`.
   Esperar CREATE_COMPLETE y verificar configuración efectiva. No crear una
   suscripción flat-rate ni un WAF en esta alternativa.
4. Subir únicamente manifest y archivos enumerados a `releases/<SHA>/`, con
   `If-None-Match: *`, SHA256, MIME y cache de 60 s. Nunca sobrescribir una release.
   Leer checksums/versiones de vuelta. Conservar recibo privado.
5. Habilitar la distribución tras verificar objetos, OAC y bucket privado.
   Comprobar HTTPS público, rutas directas, refresh, 404, headers, móvil, DEMO y atlas.
6. Publicaciones futuras: nuevo prefijo verificado, actualización de Release e
   invalidación `/*`. Revisar allowlist si cambia el conjunto de rutas. Rollback
   vuelve al prefijo anterior verificado, restaura sus Functions si cambiaron e invalida.
   Assets tienen nombres estables; durante propagación/caché puede requerirse reload.
   Versiones anteriores se conservan, no hay limpieza automática destructiva.

Retirada propia del hosting: deshabilitar distribución, esperar Deployed,
retirar distribución/functions/OAC/policy mediante su stack y conservar
el bucket. Borrar versiones/bucket necesita una decisión explícita. La retirada de
EC2/ECS/SQL/NAT del laboratorio no afecta a esta web. No se programa retirada ni se
crean automatizaciones mediante este documento. No hay suscripción Free que cancelar.

Ensayo HTTPS explícito con Chrome/Playwright existentes:

```powershell
$env:PLAYWRIGHT_MODULE='<Playwright existente>/index.mjs'
$env:CHROME_EXECUTABLE='<Chrome existente>/chrome.exe'
node portfolio/product/test-public.mjs https://<distribucion>.cloudfront.net <paquete-sellado> <evidencia-nueva>
```

GET/HEAD al hosting y datos sintéticos en memoria. Verifica todos los bytes públicos
contra manifest, MIME/CSP, cinco vistas, doce diagramas, móvil, refresh y errores.
No vuelve a probar SQL/KMS ni llama a la API; esa evidencia permanece separada en
[VALIDATION-PR36.md](VALIDATION-PR36.md). No instala herramientas automáticamente.


## Actualizar contenido del hosting existente

`publish.py update` valida el paquete reproducible y el template pay-as-you-go,
comprueba la instalación actual y permite cambiar únicamente el código de rutas
para el allowlist de assets y el parámetro `Release`. Los recursos, origen S3,
CSP/headers, OAC, bucket policy y plan deben seguir iguales. Nunca crea un stack
ni cambia a otro plan en este modo. Sube objetos con create-only, verifica sus
checksums/versiones y después actualiza el stack existente. Conserva el prefijo
anterior para rollback; no elimina versiones.

```sh
node portfolio/product/build.mjs <paquete-nuevo>
node portfolio/product/hosting/payg-template.mjs <template-nuevo>
python portfolio/product/hosting/publish.py update --profile cnp-cert-dev \
  --pricing-mode pay-as-you-go --template <template-nuevo>/template.json \
  --template-sha256 <sha256-revisado> --package <paquete-nuevo> \
  --receipt <recibo-privado-nuevo.json>
```

Esperar `UPDATE_COMPLETE` y CloudFront `Deployed`, invalidar una vez `/*` y ejecutar
`test-public.mjs` por HTTPS contra la distribución real. `verify` relee bucket,
OAC, funciones LIVE, distribución y cada versión publicada. Antes de publicar,
conservar template/parámetros anteriores y verificar que el diff contiene solo
rutas de contenido. Rollback: restaurar ese template y su `Release` anterior por
el mismo stack, esperar e invalidar; comprobar HTTPS de nuevo.
