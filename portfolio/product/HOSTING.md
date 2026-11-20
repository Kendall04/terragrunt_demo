# Hosting estático independiente

**[DEMO pública](https://d20ioz705caon7.cloudfront.net/)** ·
[Architecture Explorer](https://d20ioz705caon7.cloudfront.net/architecture)

Hosting exclusivo de ECS: navegador HTTPS → CloudFront → OAC firmado → S3 privado.
Cuenta `341936017254`, región `us-east-1`, stack `ecs-v2-portfolio-demo`, distribución
`E1PKEWJYYS672Q`. No utiliza hosting EKS, estados del runtime ni un origen API.
El sitio incluye cinco diagramas actuales y doce históricos; el runtime Sentinel
fue retirado y no es una dependencia de presentación.

## Publicación demostrada

La publicación del **10 noviembre 2026**, integrada mediante las
[PR #57](https://github.com/Kendall04/terragrunt_demo/pull/57) y
[#58](https://github.com/Kendall04/terragrunt_demo/pull/58), usó la release:

`01d3681abc61e451fc0b6a80a06d496aab079175712c9aa13ad62bba49891edd`.

El manifiesto y recibos privados de `archify-final-polish-20261110` registran
UPDATE_COMPLETE, CloudFront Deployed, checksums/versiones y Chrome HTTPS PASS:
62 assets, 17 diagramas, rutas/refresh, 404, MIME, CSP, móvil/escritorio y cero
llamadas a la API. La [validación de Archify](../../docs/interactive/CURRENT-INDEX.md)
conserva fuentes, hashes y capturas. Es evidencia fechada; no se publicó ni se
consultó AWS durante la consolidación documental del 18 noviembre.

Los [recibos iniciales del 7 noviembre](evidence/public/PUBLIC-HTTPS-QA.json)
pertenecen a la primera release de 12 diagramas. Sus bytes se conservan y no deben
interpretarse como el manifiesto de la publicación posterior.

## Recursos, costes y decisión de tarifa

El stack mantiene S3 privado/versionado, Block Public Access, OAC, bucket policy
limitada a la distribución, CloudFront y dos Functions para rutas y cabeceras.
No hay WAF propio, API Gateway, proxy AWS ni controles de infraestructura en el sitio.

La tarifa instalada es **pay-as-you-go**. El intento Free del 7 noviembre fue
rechazado por elegibilidad de recursos y revertido antes de subir archivos;
la causa específica no quedó identificada. No hay una suscripción Free que cancelar.
El cambio posterior de tarifa recibió autorización; no fue un fallback automático.

Reserva de hosting independiente: **USD 1/mes**. El modelo original de tráfico
bajo (1 GB y 10.000 requests/mes, tres paquetes pequeños) estimó USD 0,10–0,20/mes,
sin tratarlo como factura ni límite automático. Tráfico, almacenamiento/versiones,
S3, Functions e invalidaciones fuera de franquicia pueden añadir cargos. Consultar
consumo y precios vigentes antes de una nueva decisión de presupuesto.

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

Para el hosting instalado, usar `publish.py update` como se indica abajo; no crear
otro stack. Construir dos veces y comparar manifiestos, verificar el paquete y
conservar template/parámetros y prefijo anteriores antes de cambiar `Release`.
Las versiones previas permanecen disponibles; no hay limpieza destructiva automática.

La instalación inicial y el intento Free están conservados en
[el registro del 7 noviembre](https://github.com/Kendall04/terragrunt_demo/blob/1a39c46cc02f262c04f438207647acc1282393a0/portfolio/product/HOSTING.md).
Son evidencia histórica, no instrucciones para recrear la distribución.

Retirar el hosting requiere una operación distinta: deshabilitar la distribución,
esperar Deployed y retirar los recursos del stack conservando el bucket. Borrar
sus versiones necesita una decisión explícita. Apagar ECS/SQL/NAT no apaga esta DEMO.

Ensayo HTTPS explícito con Chrome/Playwright existentes:

```powershell
$env:PLAYWRIGHT_MODULE='<Playwright existente>/index.mjs'
$env:CHROME_EXECUTABLE='<Chrome existente>/chrome.exe'
node portfolio/product/test-public.mjs https://<distribucion>.cloudfront.net <paquete-sellado> <evidencia-nueva>
```

GET/HEAD al hosting y datos sintéticos en memoria. Verifica todos los bytes públicos
contra manifest, MIME/CSP, cinco páginas, cinco diagramas actuales y doce históricos, móvil, refresh y errores.
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
