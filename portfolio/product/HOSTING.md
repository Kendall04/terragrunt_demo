# Publicación posterior · solo DEMO

**Propuesta, no desplegada.** Requiere aprobación separada para crear recursos
y publicar. Independiente de ECS, SQL, NAT y del hosting EKS.

## Arquitectura mínima

Navegador → HTTPS CloudFront → OAC → bucket S3 privado exclusivo de ECS.
Block Public Access, bucket owner enforced y política de lectura limitada al
ARN de esta distribución. Assets públicos de presentación con SSE-S3; no es
necesaria una CMK adicional. Sin API origin, Lambda, credenciales del runtime,
endpoints administrativos ni proxy. Usar inicialmente el dominio CloudFront;
dominio/Route53/WAF y sus cargos no forman parte de esta propuesta.

Publicar el manifiesto y sus archivos bajo un prefijo inmutable por SHA de
contenido. Seleccionar ese prefijo como OriginPath; rollback vuelve al prefijo
anterior. Un cambio de versión requiere invalidación o vencimiento de cache
para evitar mezclar assets de distintas releases con nombres estables.
No sobrescribir a ciegas el prefijo anterior. Retener versiones revisadas.

Un rewrite de CloudFront Function puede resolver únicamente `/`, `/demo`,
`/architecture`, `/resilience`, `/evidence` y sus barras finales a sus index.
Las rutas desconocidas y `/_api/*` devuelven error real, nunca una página 200.
No transformar todos los 403/404 de S3 en `/index.html`.

Headers: HTTPS, nosniff, no-referrer y CSP del `HOSTING.json`. El shell impide
conexiones externas. Diagramas/lecturas necesitan su CSP específica embebida
(scripts/estilos inline del visor, sin red) y `sandbox=allow-scripts` opaco.
No aplicar la CSP del shell indiscriminadamente sobre los documentos Archify:
bloquearía sus scripts. Mantener policies por comportamiento/ruta, con pruebas
de iframe tras publicación. No añadir `allow-same-origin` ni `unsafe-eval`.

## Coste propuesto y procedimiento

Hipótesis inicial: ≤0,1 GB de assets/versiones, 1 GB de salida mensual y 10.000
HTTPS requests, sin dominio, WAF, logs en tiempo real ni computación. Reserva
propuesta **USD 1/mes**, no aprobada y no límite automático. Estimación de orden
de magnitud, no coste observado. Sin descontar free tier, las tarifas publicadas
de CloudFront para USA/México/Canadá modelan 1 GB × USD0,085 + 10.000 HTTPS ×
USD0,01/10.000 = USD0,095, más almacenamiento/requests S3, función e invalidaciones.
Las tarifas varían por edge y planes; recalcular antes del alta. Las franquicias
son compartidas por cuenta, no una promesa de coste cero para este sitio.
Fuentes: [CloudFront pay-as-you-go](https://aws.amazon.com/cloudfront/pricing/pay-as-you-go/)
y [S3 Pricing](https://aws.amazon.com/s3/pricing/), consultadas 7-nov-2026.

1. Aprobar bucket/distribución/OAC/function propios y reserva mensual concreta.
2. Crear IaC independiente del state de runtime y EKS, con permisos de publicación
   limitados a ese bucket/prefijo y distribución. No reutilizar roles administrativos.
3. Construir dos veces, comparar manifest, verificar ausencia de modo/proxy AWS.
4. Subir solo archivos del manifest y el manifest; verificar checksum remoto.
5. Activar el prefijo revisado y comprobar rutas, MIME, CSP, móvil, doce diagramas,
   `/_api` rechazado y cero llamadas al endpoint ECS.
6. Documentar URL, SHA, recursos, costes y procedimiento de retirada del hosting.

La retirada del runtime el 9-nov no requiere retirar este hosting futuro. La
edición AWS permanece una herramienta loopback para otra sesión autorizada;
una versión pública conectada requiere autenticación/autorización del backend.
