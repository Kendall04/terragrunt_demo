# ECS V2 · Product Demo & Architecture Explorer

Experiencia principal del portafolio ECS: texto cifrado, resiliencia y arquitectura.
La DEMO pública funciona con AWS apagado. AWS Edition es una herramienta local
supervisada, **no una web pública autenticada**.

## Abrir

**[Sitio público HTTPS](https://d20ioz705caon7.cloudfront.net/)** ·
[Product Demo](https://d20ioz705caon7.cloudfront.net/demo) ·
[Architecture Explorer](https://d20ioz705caon7.cloudfront.net/architecture) ·
[Resilience Lab](https://d20ioz705caon7.cloudfront.net/resilience) ·
[Evidence](https://d20ioz705caon7.cloudfront.net/evidence).
Solo DEMO, sin conexión a la API. [Publicación y costes](HOSTING.md).

Desde la raíz del repositorio, con Node 22+ existente (sin `npm install`):

```powershell
node portfolio/product/server.mjs
```

- <http://127.0.0.1:4182/>: plataforma, mapa de relaciones y resultados medidos.
- <http://127.0.0.1:4182/demo>: mensajes sintéticos, recorrido API → KMS → SQL → lectura.
- <http://127.0.0.1:4182/architecture>: siete vistas V2 y cinco históricas.
- <http://127.0.0.1:4182/resilience>: reproducciones visuales NAT, SQL y backups.
- <http://127.0.0.1:4182/evidence>: evidencia fechada y limitaciones.

`Ctrl+C` cierra el servidor propio. Nunca adopta ni termina un proceso ajeno.
La DEMO almacena datos en memoria de la pestaña; recargar o reiniciar restaura
dos ejemplos. No cifra, no persiste en SQL, no llama a AWS. Los recorridos
históricos avanzan a una velocidad de presentación, no de telemetría en vivo.

## Decisión frontend

Se conserva HTML/CSS y módulos ESM nativos con componentes DOM pequeños: cinco
vistas no requieren un runtime React ni un bundler. Navegación History API,
estado explícito, tipado mediante validación del contrato en los límites, cero
dependencias de producción. Los builds copian una allowlist y sellan cada archivo.

La referencia visual fue el proyecto propio
[EKS, commit f3b8039](https://github.com/Kendall04/cloud-native-eks-platform/tree/f3b80397a1cb41dbb5dcfa5df955f70c734907fb/frontend),
incluyendo App, config, API, Explorer, proxy y CSS, además de Chrome real en
`/demo` y `/architecture`. Se comparte la jerarquía de navegación, tema oscuro y
separación de modos. El rediseño usa tinta, ámbar y lavanda, Sora autoalojada y
una presentación de laboratorio de sistemas. Véase [DESIGN.md](DESIGN.md).
No se reutilizan funcionalidades Shipment/Auth ni recursos EKS. El portafolio
anterior de `portfolio/server.mjs` continúa disponible como archivo histórico.

| Módulo | Responsabilidad |
| --- | --- |
| `app.mjs`, `style.css`, `index.html` | Vistas, foco/teclado, estados y presentación responsive |
| `api.mjs` | Adaptadores independientes DEMO/AWS; contrato DTO, UTF-8 y fechas UTC |
| `data.mjs` | Recorridos y métricas históricas con límites explícitos |
| `diagrams.mjs` | Verificación de pins y derivados aislados de los diagramas aceptados |
| `server.mjs`, `proxy.mjs` | Sesión loopback opt-in para API DEV, nunca incluida en hosting |
| `build.mjs`, `preview.mjs` | Paquete estático DEMO reproducible y preview con hashes |

## AWS Edition: uso autorizado y temporal

Antes de abrirla, comprobar cuenta `341936017254`, región `us-east-1`, API
`4cjyis8dsa`/`demo-dev-edge`, autorización del laboratorio, salud, presupuesto y
ventana. El preflight real de esta entrega figura en [VALIDATION.md](VALIDATION.md).
No usa credenciales AWS en el frontend ni cambia IAM, CORS o infraestructura.

```powershell
node portfolio/product/server.mjs --aws
# Abrir el enlace temporal que imprime el proceso, incluido su fragmento #session.
```

La selección es de proceso, nunca automática ni un toggle público. El fragmento
contiene una capacidad local efímera aleatoria, **no un token AWS**; desaparece
de la URL al cargar y solo permanece en memoria. No compartir ese enlace.
Recargar pierde la capacidad. Cerrar el proceso termina la sesión.

Salvaguardas comprobadas:

- Bind exclusivo `127.0.0.1`, Host exacto, Origin/Sec-Fetch-Site, token 256 bits,
  sesión de 15 minutos y caducidad absoluta `2026-11-09T04:00:00Z`.
- Destino HTTPS fijo. Solo GET liveness/readiness/text y POST text; sin URLs,
  paths, headers o métodos arbitrarios, sin redirects ni retries.
- 60 solicitudes / dos escrituras / dos solicitudes simultáneas por sesión;
  página 1–20, tamaño 1/5/10, sin enumeración automática.
- 4096 bytes UTF-8 por texto, respuesta ≤128 KiB, timeout upstream 10 s;
  ninguna respuesta fallida se sustituye por DEMO. Una escritura incierta se
  reconcilia con lecturas, nunca se reintenta automáticamente.
- Ningún token en registros de solicitudes, localStorage, cookies, Git o paquete público. El recibo
  registra método, ruta, estado y duración; no payload ni headers.
- El CLI cierra al expirar. No ejecutar pruebas durante la reserva de retirada
  del 9-nov 02:30 UTC. Una sesión posterior requiere una ventana y endpoint
  revisados; cambiar fechas en el código no concede autorización.

**Límite de seguridad:** la API DEV original sigue siendo pública y no autentica
usuarios. El proxy restringe esta herramienta local; no protege el endpoint
upstream contra terceros ni sirve como autenticación de producción. Una edición
AWS pública requeriría autorización real en backend (identidad y acceso a datos)
y revisión separada. CORS, CloudFront o una API key dentro del bundle no bastan.
No se implementó LOCAL: no aporta valor adicional al objetivo y evita destinos
arbitrarios. El laboratorio solo admite texto sintético no sensible.

Contrato: POST `/text` → 200 `{id,text,createdAt}`; GET paginado → array; los
timestamps sin zona de SQL son UTC por `DateTime.UtcNow` del controlador. El
navegador verifica ID/texto y muestra UTC; no conoce el ciphertext SQL.

## Atlas y evidencia

Se consumen [los siete mapas aceptados](../../docs/interactive/V2-INDEX.md), sus
JSON, hashes y hojas de lectura sin editar los originales. `adaptArchify`
genera únicamente una copia de presentación, con tema oscuro, cámara y mensajes
de selección. El SVG original permanece; no se atribuye al generador el shell.

Los iframes usan `sandbox="allow-scripts"` sin `allow-same-origin`, CSP sin red,
sin exportación/enlaces internos ni acceso al host. El host valida ventana de
origen opaca y node ID contra catálogo antes de mostrar fuentes Git fijadas.
Zoom, pan y ajuste son del adaptador existente. En móvil: explorar una zona,
usar hoja de lectura o alternativa textual; no prometer legibilidad simultánea
de una arquitectura completa a 390 px. Las categorías IMPLEMENTADO/DESPLEGADO/
DEMOSTRADO/HISTÓRICO/NO VALIDADO son estados fechados, no salud actual.

La continuidad 12–24 h de Sentinel tiene seguimiento independiente. Esta tarea
no la certifica ni modifica sus timers, journals o infraestructura.

## Paquete estático independiente

```powershell
node portfolio/product/build.mjs logs/ecs-demo-build-01
node portfolio/product/preview.mjs logs/ecs-demo-build-01
# http://127.0.0.1:4183/demo
```

El directorio debe ser nuevo/vacío. `MANIFEST.json` fija bytes y SHA256; dos builds
con las mismas fuentes producen el mismo manifiesto. No depende de rutas del
equipo, hora ni Git metadata. Solo incluye DEMO, assets, catálogo, JSON y derivados
de diagramas. No incluye servidor, proxy, test runners, recibos privados o sesión
AWS. `HOSTING.json` especifica rutas/headers; [HOSTING.md](HOSTING.md) detalla la
publicación real independiente. El preview comprueba hashes antes de servir.

## Pruebas

```powershell
node --test portfolio/test-contract.mjs
# Incluye la suite histórica y las pruebas V2; corre en CI - Repo Hygiene.

# Chrome/Playwright existentes; no instala ni descarga herramientas.
$env:PLAYWRIGHT_MODULE='<ruta absoluta a playwright/index.mjs>'
$env:CHROME_EXECUTABLE='<ruta absoluta a chrome.exe>'
$env:UI_EVIDENCE_DIRECTORY='<directorio nuevo de evidencia>'
node portfolio/product/test-browser.mjs
```

El runner de navegador usa DEMO y dobles HTTP explícitos; bloquea toda red
externa. Prueba responsive, foco, XSS literal, 12 diagramas, zoom/fit, aislamiento,
paquete estático, errores/timeout/offline y ausencia de fallback. No es una
certificación WCAG ni prueba de todos los navegadores; revisar capturas.

Prueba AWS manual, **fuera de CI**, después del preflight:

```powershell
$env:ECS_AWS_BROWSER_TEST='CONFIRMED_DEV_SYNTHETIC'
$env:UI_EVIDENCE_DIRECTORY='<directorio privado nuevo>'
# Un único POST solo cuando esté expresamente autorizado; no repetir por fallo.
node portfolio/product/test-aws-browser.mjs --write-once
# Reconciliación limitada a cinco registros, sin otra escritura:
$env:ECS_PRIOR_AWS_RECEIPT='<receipt.private.json del POST>'
node portfolio/product/test-aws-browser.mjs --readback
```

El runner guarda recibo sin payload y captura ocultando textos ajenos. No hace
cambios AWS de configuración, fallos de infraestructura o limpieza de datos.
Los resultados mock y reales están separados en [VALIDATION.md](VALIDATION.md).
