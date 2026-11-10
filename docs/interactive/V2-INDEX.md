# ECS V2: atlas técnico de DEV

> Current ECS architecture: [CURRENT-INDEX.md](CURRENT-INDEX.md). This atlas is a preserved historical snapshot; Sentinel is now independent and DEV CD is automatic.


Revisión de implementación: `5d35edef4f2ee1c0463df483d22745d13cae47cd`.
Inventario AWS de solo lectura: **6 noviembre 2026, 23:13:40 UTC**,
cuenta `341936017254`, `us-east-1`. Estas vistas son fotografías fechadas,
no un dashboard ni una garantía de disponibilidad. No se modificó AWS para
adaptarlo a los dibujos. La vigilancia de 12–24 horas sigue siendo un trabajo
independiente: este atlas no acredita su terminación.

## Recorrido recomendado

La **hoja de lectura** conserva el SVG oficial íntegro, permite ampliarlo y
presenta todas las relaciones como texto con fuentes. En móvil, deslice el
diagrama; la vista completa sirve para orientarse. El HTML **Archify** conserva
su visor original. Ninguno de estos archivos se integró en la UI del portafolio.

| Vista | Pregunta que responde | Formatos y fuente editable |
| --- | --- | --- |
| Plataforma | ¿Por dónde pasan una petición, el dato cifrado y la evidencia? | [Lectura](readable/v2-platform.html) · [Archify](v2-platform.html) · [JSON](source/v2-platform.json) |
| Red por zona | ¿Dónde están SQL, ECS y la sonda; qué recupera cada NAT? | [Lectura](readable/v2-network.html) · [Archify](v2-network.html) · [JSON](source/v2-network.json) |
| Sentinel interno | ¿Quién observa, persiste, evalúa, archiva y notifica? | [Lectura](readable/v2-sentinel.html) · [Archify](v2-sentinel.html) · [JSON](source/v2-sentinel.json) |
| Incidente NAT | ¿Qué ocurrió realmente en el tercer ensayo y cuánto tardó? | [Lectura](readable/v2-nat-incident.html) · [Archify](v2-nat-incident.html) · [JSON](source/v2-nat-incident.json) |
| Recuperación SQL | ¿Cómo se sustituye el único escritor sin split-brain? | [Lectura](readable/v2-sql-recovery.html) · [Archify](v2-sql-recovery.html) · [JSON](source/v2-sql-recovery.json) |
| Confianza | ¿Qué identidad cruza cada frontera y qué riesgo permanece? | [Lectura](readable/v2-trust.html) · [Archify](v2-trust.html) · [JSON](source/v2-trust.json) |
| Entrega y ownership | ¿Qué administra Terraform, qué hace el operador y qué está inhibido? | [Lectura](readable/v2-delivery.html) · [Archify](v2-delivery.html) · [JSON](source/v2-delivery.json) |

La cronología NAT utiliza **Timeline de Archify**, no un diagrama de secuencia
sincrónico: son mediciones de sistemas distintos, con resolución y muestreo
diferentes. Los otros seis son vistas Architecture. Las flechas expresan
solicitudes, transferencia o autoridad según su etiqueta; las respuestas están
implícitas. Una flecha rosa identifica un control de seguridad, **no asegura
que todo ese enlace sea TLS**. El violeta discontinuo distingue eventos o vínculos
inhibidos explícitamente rotulados; la etiqueta precisa su significado. Un cruce
de rutas gráficas no es una unión.

## Estados de evidencia

- **IMPLEMENTADO:** contrato presente en código; no prueba instalación ni ejecución.
- **DESPLEGADO:** configuración leída en AWS en el inventario o en un recibo fechado citado.
- **DEMOSTRADO:** ejecución auténtica documentada, con alcance y limitaciones.
- **HISTÓRICO:** revisión o ensayo anterior, preservado con su procedencia.
- **NO VALIDADO:** falta evidencia suficiente; no debe inferirse de un componente vecino.

Las etiquetas adicionales `LÍMITE` e `INHIBIDO` describen condiciones, no un
nuevo nivel de certificación. Los cinco Archify originales siguen en
[el índice histórico](README.md). Sus JSON, HTML, pins y `GENERATION.json` no
se regeneraron ni se reinterpretaron como V2.

## Evidencia y revisión

- [Auditoría individual y matriz de discrepancias](V2-AUDIT.md).
- [Trazabilidad de cada nodo, relación y fragmento de fuente](TRACEABILITY-V2.json).
- [Snapshot AWS saneado](evidence/AWS-SNAPSHOT-20261106.json): incluye alcance de las lecturas; no secretos ni estado Terraform bruto.
- [Generación y hashes V2](GENERATION-V2.json), separados de la procedencia histórica.
- [Regeneración, controles y revisión visual](V2-VALIDATION.md).
- [Recuperación y revisión de seguridad](../V2-RECOVERY-SECURITY-20261105.md), [ensayos Sentinel](../SENTINEL-CHAOS-20261106.md) y [límites de confianza](../V2-TRUST-AND-THREATS.md).

Las fuentes de cada figura están enlazadas al **commit revisado**, no a `main`
móvil. La trazabilidad registra el hash del fragmento citado y el de los archivos
de implementación revisados. Un cambio posterior exige volver a revisar sus
afirmaciones; no se actualizan hashes para aparentar validación.

## Límites que deben acompañar las imágenes

Una tarea blue y un SQL activo no constituyen HA de aplicación/base. Dos NAT
no eliminan esos puntos únicos. La recuperación SQL es fría y supervisada, no
un failover automático. CROSS-AZ observó **41m31.5s** incluyendo reparaciones;
SAME-AZ **24m42.6s**, incluyendo reboot. El backup final de un corte planificado
no demuestra RPO cero ante pérdida abrupta. No existe una cadena PITR instalada.

La API DEV es pública y no autentica usuarios. TLS termina en API Gateway;
VPC Link → ALB → aplicación usa HTTP privado. SQL sí valida TLS, hostname y el
certificado público autofirmado de laboratorio. El rol del host puede acceder
a más recursos que el usuario SQL runtime: son fronteras diferentes.

Sentinel observa HTTPS únicamente desde privada A. ASG/E13 repone la NAT y
repara EIP/ruta/SDC; Sentinel no tiene ese papel. El fallo NAT corto produjo
incidente y correo de resolución, **no un correo de caída**: la escalación se
canceló legítimamente. `Unknown` por throttling sigue siendo evidencia insuficiente.

Lifecycle retira únicamente pares admitidos del nuevo prefijo. Los dos últimos
pares verificados permanecen sin etiqueta de expiración; los prefijos protegidos
no se incorporan a esta regla. No hay borrado atómico backup/manifiesto, plazo
físico exacto de eliminación ni Object Lock. El CLI de copia independiente fuera
TTL está implementado; restaurar desde ese hold bajo Lifecycle sigue pendiente
de prueba específica.

## Organización posterior del portafolio

Usar V2 como colección principal: plataforma → Sentinel → incidente → SQL,
con red, confianza y entrega como vistas de detalle. Mantener una sección
separada «Historia y ensayos retirados» para V1/az6/piloto. Mostrar fecha,
estado y límites junto al diagrama, nunca solo una insignia PASS. Esta tarea
no implementa esa navegación, landing, hosting ni diseño del portafolio.
