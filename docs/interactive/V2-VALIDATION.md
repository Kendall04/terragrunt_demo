# Generación, reproducción y revisión visual V2

## Herramienta y autoría

Se descargó el ZIP oficial **Archify 3.1.0**, commit
`1c2b42d660e4a7571813fb43839c79e3e9ca7720`, 5.017.500 bytes,
SHA256 `ffedc53390c9da6e859f41e432c5d2d0615a23cf00a503181f07efbba88a7ce8`.
Origen exacto y hashes constan en [GENERATION-V2.json](GENERATION-V2.json).
No hubo instalación global, actualización de Archify ni instalación de paquetes.
Se conserva la [licencia original](ARCHIFY-LICENSE.txt).

Los siete HTML `v2-*.html` fueron producidos **íntegramente por la herramienta
oficial**, con sus fuentes JSON. La hoja `readable/` es otro artefacto, generado
por `scripts/diagrams/readable.mjs`: extrae sin modificar el SVG y añade lectura
textual/ampliación responsive. No se atribuye esa presentación adicional a
Archify ni se modifica el HTML oficial. Tampoco es una modificación del portafolio.

## Resultado verificable

| Control | Resultado / evidencia |
| --- | --- |
| Siete grafos | `validate`, `deliver`, `check`, `browser-check`: PASS showcase, cero diagnósticos; [recibo saneado](evidence/ARCHIFY-GATES.json) |
| Segunda generación completa | **7/7 HTML idénticos byte por byte**; [REPRODUCTION.json](evidence/REPRODUCTION.json) |
| Fuentes y relaciones | 78 nodos/eventos, 67 relaciones, 54 fragmentos fijados; 26 archivos de implementación vigilados por hash LF |
| Contratos nuevos | Seis tests Node PASS: integridad, grafos inválidos, fuentes fuera de scope, SVG activo/CSS externo, límites Sentinel y lectura textual |
| CI existente | `scripts/tests/reproducibility/test_diagrams.py` ejecuta esos tests en Repo Hygiene; no se altera el workflow ni se instala Archify en CI |
| Navegador real | Chrome, 1440×1000 y 390×1000: 28 vistas completas + 14 detalles móviles, cero solicitudes externas, cero overflow de página/texto, controles fit/zoom comprobados |
| SVG original | La extracción de cada hoja es byte-identical al SVG del HTML oficial; comprobado en tests |
| Capturas | [Recibo con hashes](evidence/screenshots/BROWSER-QA.json); cada captura está vinculada al hash de su HTML |
| Históricos | Cinco HTML/JSON y dos PNG preservados; quinta fuente tiene diferencia LF/CRLF documentada en la auditoría |
| AWS | Lecturas de configuración exclusivamente; snapshot fechado, no ensayo ni modificación operativa |

Las capturas son evidencia de una sesión Chrome, no imágenes deterministas entre
versiones de navegador/OS. La reproducibilidad byte por byte corresponde al
HTML/SVG y a la hoja de lectura. El recibo de captura no sustituye inspección visual.

## Revisión perceptual

Se inspeccionaron las siete vistas de escritorio, sus detalles móviles y los
cinco originales históricos; también los dos PNG antiguos. Se verificaron
etiquetas, puntas de flecha, separación de funciones, cuadros y leyendas.

| Vista | Resultado de revisión y límite explícito |
| --- | --- |
| Plataforma | Camino de entrada y dependencia SQL/KMS inequívocos. El aviso rodea el archivo: no lo atraviesa ni convierte S3 en un relay SNS. |
| Red | Marcos VPC/AZ y destinos por zona correctos. Un cruce gráfico resuelto entre EIP A y ruta B; sin punto de unión ni dependencia A→B. |
| Sentinel | Ingestión y evaluación separadas; cleanup y watchdog distintos. El email rodea CloudWatch; CloudWatch no procesa el aviso de dominio. |
| SQL | Flujo ordenado, backup final visible; el CLI pin fuera TTL está IMPLEMENTADO. Su uso en una restauración bajo Lifecycle sigue NO DEMOSTRADO, distinto de la recuperación fría ya probada. |
| Confianza | Execution role, task role, host y login SQL separados. Las relaciones representan autoridad/uso; no implican que IAM sea autenticación SQL. |
| Entrega | Caminos nativos e inhibidos diferenciados. Dos recorridos periféricos largos conservan el significado; ningún cruce ambiguo. |
| Incidente NAT | Escala temporal, carriles y textos sin colisiones. Gmail usa segundos; ACK durable SNS no se presenta como instante de envío. |

La vista global de Archify a 390 px reduce el detalle y puede recortar su barra
de herramientas dentro del visor. Se preservó ese original y se ofrece una hoja
de lectura accesible: pan horizontal para el SVG, botones de escala y tarjetas
con todas las relaciones/fuentes. No se afirma que el grafo entero sea legible
simultáneamente en 390 px ni una certificación WCAG.

Capturas de muestra:

- [Sentinel escritorio](evidence/screenshots/v2-sentinel-reading-1440.png) y [texto móvil](evidence/screenshots/v2-sentinel-mobile-text.png).
- [Red por AZ](evidence/screenshots/v2-network-reading-1440.png).
- [Cronología NAT](evidence/screenshots/v2-nat-incident-reading-1440.png).
- [Recuperación SQL](evidence/screenshots/v2-sql-recovery-reading-1440.png).
- [Confianza](evidence/screenshots/v2-trust-reading-1440.png) y [entrega](evidence/screenshots/v2-delivery-reading-1440.png).

## Reproducir sin tocar AWS

Desde la raíz, con una copia **ya autenticada y extraída** del ZIP oficial:

```text
python scripts/diagrams/reproduce.py --tool-zip <archify.zip> --tool-root <carpeta/archify> --node <node> --evidence-dir <directorio-nuevo>
node scripts/diagrams/readable.mjs --check
node --test scripts/diagrams/test-diagrams.mjs
python -I -B -m unittest discover -s scripts/tests/reproducibility -p test_diagrams.py -v
```

`reproduce.py` verifica ZIP y todos los archivos extraídos, exige las fuentes
selladas, ejecuta serialmente el finalizador y compara con los hashes revisados.
No descarga herramientas, no actualiza pins y falla si cambian los bytes. Para
editar una figura, cambie primero su JSON, vuelva a contrastar las afirmaciones
y use el comando oficial con un directorio de evidencia nuevo:

```text
node <archify>/bin/archify.mjs finalize <architecture|timeline> docs/interactive/source/<id>.json docs/interactive/<id>.html --repo-root . --quality showcase --out-dir <evidencia-nueva> --json
```

Solo después de revisar esos recibos se actualiza `GENERATION-V2.json`, su
trazabilidad y las capturas. La procedencia original `GENERATION.json` y los
pins del portafolio se mantienen independientes. Las fuentes/artefactos V2 están
fijados a LF en `.gitattributes` para evitar falsos cambios de hash entre sistemas.

La reproducción se ejecutó con Node **24.22.1** y Chrome ya disponibles localmente.
Node 22.13 en este Windows falló en el protocolo de identidad de archivos de
Archify; no se desactivó ese control. Un intento posterior encontró `EBUSY` al
liberar un lock local de Archify: se conservó el recibo, se comprobó que su PID
había terminado y se retiraron solo sus dos locks exactos, según el contrato
oficial. No eran locks Terraform. La generación/reproducción final pasó completa.

La suite no modificada del portafolio pasó 17/18 localmente con Node 22 y 24; el test
HTTP de presentación terminó con `ECONNRESET`, también fuera del sandbox. No se
alteró el servidor ni se omitió el test. El [CI normal en Ubuntu de la PR #35](https://github.com/Kendall04/terragrunt_demo/actions/runs/42314949659/job/128225225085),
revisión `81723398c79eaed9a79b9b2791346bc7603ae305`, completó correctamente esa
suite y el paso de reproducibilidad que incluye los seis tests nuevos. Esto
distingue el fallo local del resultado remoto; no atribuye una causa no demostrada.
El estado final de todos los controles y la integración se consulta en la
[PR #35](https://github.com/Kendall04/terragrunt_demo/pull/35).

La primera aceptación global rechazó seis `UNMODELED_SOURCE`: los cinco helpers
de diagramas y su wrapper de pruebas. Se registraron únicamente esas seis
entradas con el scanner original, conservando `semantic_status=UNVERIFIED` y
todas las entradas previas intactas. Son hashes de cobertura, no una nueva
aprobación de seguridad. La verificación del inventario sobre una copia de los
archivos versionados pasó; el historial del primer CI fallido permanece visible.

Capturas opcionales, con Playwright y Chrome existentes, sin instalar dependencias:

```text
PLAYWRIGHT_MODULE=<ruta absoluta a playwright/index.mjs>
CHROME_PATH=<ruta absoluta a Chrome>
node scripts/diagrams/capture.mjs <directorio-de-capturas>
```

Son variables de entorno, no argumentos secretos. El script abre solo archivos
locales, bloquea solicitudes externas y comprueba overflow, fit y zoom. Las
capturas y el recibo definitivos se conservan juntos.

## Contraste con semántica AWS

El código y los readbacks determinan la instalación. La documentación oficial
se utilizó para contrastar tres interpretaciones que pueden inducir errores:

- [Integración privada HTTP API](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-private.html): conexión al listener por VPC Link, HTTP salvo configuración TLS explícita.
- [Execution role ECS](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_execution_IAM_role.html): permisos del agente para imagen/logs/secreto, distintos de credenciales del task role disponibles a la aplicación.
- [Expiración S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/lifecycle-expire-general-considerations.html): en bucket versionado, expiración corriente crea delete marker; versiones no actuales requieren su acción separada. No equivale a borrado físico inmediato ni protección Object Lock.
