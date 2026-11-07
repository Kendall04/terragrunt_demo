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
  stack, plan FREE y hashes/licencia de fuentes. La suite existente CI de higiene
  importa estas pruebas mediante `portfolio/test-contract.mjs`.

Los recibos y capturas originales de PR #36 se preservan. Las capturas nuevas
están en `evidence/redesign/`. Las tres iteraciones locales corrigieron separación
de red en el mapa, menú a 320 px y áreas táctiles, sin modificar diagramas Archify.

## Publicación

El propietario autorizó una publicación del stack y reserva de USD 1/mes,
separada del laboratorio, con template revisado
`2cfaad42bf57a86e64d69fd7fa8426a05ee6a8a2e9b72c4a84cc10e575c84952`.
Se exige suscripción FREE/ACTIVE, checksum de cada objeto y pruebas HTTPS reales
antes de declarar publicación PASS. El estado final y URL se registran en
[HOSTING.md](HOSTING.md); no se confunde CREATE_COMPLETE con verificación de UI.

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
