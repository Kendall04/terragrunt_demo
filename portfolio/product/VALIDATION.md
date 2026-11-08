# Cloud Resilience Laboratory — validación del rediseño

Base PR #36: `21701c91026c0b6b4de7afff0175c529a2d0995e`.
La prueba auténtica navegador → API → SQL/KMS sigue conservada en
[VALIDATION-PR36.md](VALIDATION-PR36.md) y [AWS-VALIDATION.json](evidence/AWS-VALIDATION.json).
No se repitió un POST AWS para justificar un cambio visual. El backend, proxy,
adaptadores, datos históricos, diagramas originales y sus pins no cambian.

## Pruebas locales

- [Chrome final](evidence/BROWSER-QA.json): **PASS**, 57 capturas, cero errores JS,
  cero llamadas externas. DEMO crear/leer/reset/XSS literal; errores HTTP503,
  timeout, pérdida de conexión y expiración de AWS Edition con dobles explícitos.
- Doce diagramas en escritorio/móvil, zoom, ajuste, opaque sandbox, inspector,
  fuentes y lectura adaptable. Navegación teclado/skip/foco/Escape.
- Cinco resoluciones: 320, 390, 768, 1440, 1920 px; cinco vistas sin overflow.
- [Auditoría de diseño](DESIGN-AUDIT.md): contraste, semántica, tamaño táctil y
  reduced motion PASS en 25 combinaciones. No equivale a certificación WCAG.
- [Manifest actual](evidence/STATIC-MANIFEST.json):
  `3ede367cc3a7e4d48c8fa1d0fc2f66ef75be9ebf8e34d74299d86d9dda6b9b21`.
  Build reproducible, edición DEMO fija, sin proxy, credenciales o conexiones API.
- Se añadieron pruebas de allowlist CloudFront, CSP diferenciada, aislamiento del
  stack, alternativas Free/pay-as-you-go y hashes/licencia de fuentes. CI de higiene
  importa estas pruebas mediante `portfolio/test-contract.mjs`.

Los recibos y capturas originales de PR #36 se preservan. Las capturas nuevas
están en `evidence/redesign/`. Las tres iteraciones locales corrigieron separación
de red en el mapa, menú a 320 px y áreas táctiles, sin modificar diagramas Archify.

## Publicación

**PASS** en [CloudFront real](https://d20ioz705caon7.cloudfront.net/).
AWS rechazó Free; tras rollback y autorización nueva se instaló pay-as-you-go,
template `11fd9d4ad78a290a3c0d9e4ed20088484475ed8062e94bdebf3323316c0de3fe`,
manteniendo la reserva separada USD 1/mes. [HOSTING.md](HOSTING.md) conserva el fallo,
la decisión, recursos, coste modelado y rollback.

[Recibo HTTPS](evidence/public/PUBLIC-HTTPS-QA.json): 47 archivos públicos idénticos
al manifest sellado, MIME/CSP correctos; cinco vistas en 320/390/768/1440/1920;
navegación directa, refresh, menú, foco y skip link; doce diagramas desktop/móvil,
zoom/fit/sandbox/lectura; CRUD/reset DEMO y tres reproducciones históricas.
Cero errores JS, cero solicitudes externas o al API. Se revisaron capturas
auténticas públicas de portada y Product Demo móvil, además de la revisión local.

[Readback AWS](evidence/public/HOSTING-READBACK.json): UPDATE_COMPLETE,
Deployed/Enabled, 48 objetos con checksum/versionId, S3 privado/versionado/cifrado,
OAC firmado, bucket policy limitada y Functions idénticas al template. No se
apagó el runtime para esta comprobación: la independencia se demuestra por
origen estático único, edición fija, CSP y ausencia de solicitudes, no por un
teardown inventado.

El primer CI detectó `UNMODELED_SOURCE` para el publicador Python nuevo. Se registró
únicamente ese archivo en el inventario existente, con digest real y disposición
UNVERIFIED; no se alteraron tests, contratos ni recursos E1. La suite de contratos
del portafolio pasó en Linux. Dos solicitudes de HTML grandes dieron ECONNRESET
en Node local Windows; Chrome local/público y CI Linux completaron esos recorridos.

## Reproducir sin AWS

```powershell
node --test portfolio/test-contract.mjs
node portfolio/product/build.mjs <directorio-nuevo-vacio>
node portfolio/product/preview.mjs <directorio-generado>
```

Chrome existente + Playwright existente, sin instalación automática:

```powershell
$env:PLAYWRIGHT_MODULE='<ruta/index.mjs>'
$env:CHROME_EXECUTABLE='<ruta/chrome.exe>'
$env:UI_EVIDENCE_DIRECTORY='<directorio-nuevo-vacio>'
node portfolio/product/test-browser.mjs
node portfolio/product/audit-design.mjs <recibo-nuevo.json>
```

Las pruebas de navegador usan DEMO y dobles locales; no invocan el API AWS.
El generador de hosting es offline. `hosting/publish.py` sí muta AWS cuando se
elige create/upload/enable y requiere autorización de propietario; no forma parte
de CI ni se ejecuta por abrir esta documentación.
