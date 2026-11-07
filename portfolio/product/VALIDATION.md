# ECS V2 UI · validación del 7-nov-2026

Base revisada: `a46636d6b0b9f38bdbe2512f54cb75d99b406e8d` (PR35).
El cambio es frontend/documentación/pruebas. No modifica diagramas originales,
Terraform funcional, IAM, runtime ECS, SQL, NAT o Sentinel. EKS se consultó como
referencia de solo lectura.

## API AWS auténtica: PASS

[Recibo saneado](evidence/AWS-VALIDATION.json) y
[captura final](evidence/aws-real-desktop.png). Sin credenciales ni cuerpos de
otros registros. No hay fallback, mock o almacenamiento local en esta prueba.

Preflight `2026-11-07T01:03:12.869890Z`: STS administrador en cuenta
`341936017254`, región `us-east-1`; API ID `4cjyis8dsa`, nombre `demo-dev-edge`,
HTTPS endpoint original y cuatro rutas verificadas. Blue ACTIVE 1/1 revisión15;
green ACTIVE 0/0 revisión9. Liveness/readiness 200, SQL y KMS Healthy. Esto es una
lectura fechada, no garantía de disponibilidad futura ni nueva auditoría AWS.

| Petición desde Chrome | UTC | HTTP | Duración |
| --- | --- | --- | --- |
| GET `/health/live` | 01:10:07.711 | 200 | 332 ms |
| GET `/ready` | 01:10:08.049 | 200 | 464 ms |
| POST `/text` | 01:10:08.596 | 200 | 126 ms |
| GET `/text?page=1&pageSize=5` | 01:10:08.746 | 200 | 138 ms |

Un único mensaje sintético, ID **6**, creado a `01:10:08.7073381Z`.
SHA256 del texto: `5622a688df8000e5ce2d0755e3037d56cebc7bc4720b92a3858303d53e3aace5`.
ID y contenido coinciden en POST, GET y DOM. Se respetó la paginación; no se
enumeraron todas las páginas ni se borraron registros.

Readback final **01:25:08–01:25:09 UTC**: tres GET 200, mismo ID/hash y fecha UTC
correcta bajo zona de navegador Costa Rica. Cero POST adicionales. El código
del backend cifra/persiste/descifra; readiness comprueba sus dependencias. La
UI no inspecciona ciphertext ni afirma haber leído directamente SQL o CloudTrail.

Se conservó un fallo intermedio del runner: esperaba `T` en la fecha cuando el
DOM presenta un espacio y `UTC`. Sus tres GET fueron 200; se corrigió la aserción,
no el backend. La primera versión de UI también había interpretado la fecha
sin sufijo de zona como hora local; el adaptador ahora respeta el contrato UTC
de `DateTime.UtcNow`, con test específico y readback final. No se ocultan ambos
hallazgos ni se confunden con un fallo de SQL/KMS.

**Coste:** 12 peticiones HTTP reales contando dos preflight, cuatro iniciales y
dos lecturas de tres; un solo POST. Modelo incremental conservador USD0,02,
USD14,72/20 acumulados según el modelo previo. No hay gasto facturado atribuible
observado ni nuevos recursos. Ventana preservada: reserva 9-nov 02:30 UTC y cierre
04:00 UTC. No quedan procesos proxy AWS abiertos por estos tests.

## DEMO, contratos y navegador

12 tests nuevos cubren memoria/paginación/reset, contrato/UTC, UTF-8, errores,
ausencia de retry/fallback, rutas y origen/capacidad local, expiración, carrera
de POST concurrentes, pins/sandbox, reproducibilidad y preview contra alteraciones.
Se ejecutan junto con los 18 tests históricos mediante `portfolio/test-contract.mjs`
en el job existente CI - Repo Hygiene. El test AWS manual no se importa en CI.

Las primeras 11 pruebas nuevas pasaron en una ejecución local de la suite combinada.
La suite focalizada final, incluyendo errores upstream no JSON y comparación
de manifiesto/capturas con sus bytes, terminó **12/12 PASS**.
Otras ejecuciones Windows presentaron `ECONNRESET` intermitente al descargar el
HTML grande de Sentinel desde el preview (10/11); la suite histórica también
falló al servir sus HTML grandes (28/29 en la ejecución combinada, Node22 y
Node24). No se omitió ni debilitó ningún gate. El resultado remoto Linux
debe verificarse en la PR antes de integrar. Chrome sí abrió los doce documentos
en escritorio y móvil. Los resultados remotos de la integración están enlazados
en la PR asociada a este cambio.

[BROWSER-QA.json](evidence/BROWSER-QA.json): **PASS**, 36 capturas, cero requests
externos y cero errores JavaScript. La suite se ejecutó sobre Chrome real con
Playwright existente; las fallas HTTP503, timeout y desconexión son **dobles
identificados**, no interrupciones de AWS. Se comprobaron:

- Mensajes DEMO como texto literal (incluido payload XSS), reset, cero llamadas API.
- Skip link, foco al navegar, navegación por teclado, modo visible.
- Vistas en 320/390/768 px, sin overflow horizontal del host.
- Doce diagramas a 1440 y 390 px: nodos, zoom/fit y sandbox opaco; inspector,
  fuentes verificadas, lectura alternativa y hoja adaptable.
- Tres replays con paso/pausa/reset y límites históricos visibles.
- Modo AWS con fallos HTTP, timeout, pérdida de conexión y capacidad perdida al
  recargar: nunca aparecen registros sintéticos como sustituto.
- Paquete estático servido desde sus propios bytes: rutas directas, creación y
  consulta DEMO, diagramas aislados, sin backend.

Revisión visual: se corrigieron un skip link visible en la captura completa,
una carrera de captura mientras cargaba el iframe, una colisión de clases en
la cronología y navegación móvil cortada. Capturas finales:

| Vista | Escritorio | Móvil |
| --- | --- | --- |
| Product Demo | [workspace](evidence/desktop-product.png) | [390 px](evidence/mobile-demo.png) |
| Architecture | [Sentinel](evidence/desktop-explorer.png) | [390 px](evidence/mobile-explorer.png) |
| Resiliencia | [NAT](evidence/desktop-resilience-nat.png) | [390 px](evidence/mobile-resilience.png) |
| Evidencias | [fuentes en la UI](app.mjs) | [390 px](evidence/mobile-evidence.png) |
| AWS | [readback auténtico](evidence/aws-real-desktop.png) | No se repitió el POST en móvil |

No es certificación WCAG completa ni prueba de Safari/Firefox. La arquitectura
global requiere zoom o lectura textual en móvil; no se reduce a etiquetas
ilegibles como único modo de acceso. Todas las capturas de diagramas se conservan
junto al recibo, con SHA256.

## Reproducibilidad y alcance

[STATIC-MANIFEST.json](evidence/STATIC-MANIFEST.json): 43 archivos, 11.868.091 bytes,
content SHA256 `411fb3e06c4a030beeea29990fe89c0c6e2a3c4ce8a451893844492f223cf3e6`.
El manifiesto enumera cada archivo; dos builds de las mismas fuentes comparan
igual. No incluye evidencia privada, servidor, proxy ni selector AWS. Los
originales Archify, JSON, `GENERATION-V2.json`, `TRACEABILITY-V2.json` y pins
permanecen byte-identical. Las fuentes públicas del inspector están fijadas a
commits del atlas, no a una rama mutable.

La reserva de hosting futuro **no está aprobada**. DEMO puede publicarse tras
revisar [la propuesta independiente](HOSTING.md); AWS Edition permanece local.
No se abre ni mantiene infraestructura para sostener una presentación visual.
No se repiten ensayos de recuperación ni se certifica continuidad de Sentinel.
