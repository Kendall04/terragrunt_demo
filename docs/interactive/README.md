# ECS · diagramas Archify

Cinco HTML generados por **Archify 3.1.0**, no dibujos propios atribuidos a Archify:

1. [Aplicación V1 histórica](v1-platform.html): API Gateway, VPC Link, ALB, Fargate, SQL/KMS.
2. [Red V1 histórica](v1-network.html): red privada y NAT Instances; sin failover entre zonas demostrado.
3. [Ensayo az6 retirado](az6-recovery.html): SQL/API entre zonas; destino preparado, dos reparaciones; no ECS/ALB.
4. [Señales locales de backup](backup-signals.html): recibos y evaluación local, sin entrega externa.
5. [Backups y Sentinel](future-integrations.html): observador/adaptador/política local con memoria de prueba; instalación, persistencia real y correo pendientes. PKI fuera de ECS.

La [demo local](../../portfolio/README.md) integra los cinco con cámara/zoom y
etiquetas de estado. Los JSON editables están en source/. [GENERATION.json](GENERATION.json)
registra herramienta, commit, hashes y gates; [licencia MIT](ARCHIFY-LICENSE.txt).
Los originales no se modifican para incrustarlos: el servidor comprueba sus hashes,
elimina metadata privada/enlaces de la copia de presentación y aplica CSP sin red.
El iframe opaco permite scripts locales del visor, sin same-origin ni acceso a la
página principal. La cámara reutiliza el patrón de EKS; exportación desactivada en
esta copia aislada. En móvil se usa zoom para leer, con Ajustar todo para volver.

Procedencia: versión y autor coinciden con docs/maintenance.md de EKS. El paquete
oficial tt-a1i/archify v3.1.0 corresponde al commit
1c2b42d660e4a7571813fb43839c79e3e9ca7720. Se ejecutó desde task-3, sin instalación
global, npm install ni cambio al toolchain. Los gates de cada original finalizaron
validate/deliver/check/browser-check PASS. El origen migrado de ECS es un bundle;
una copia sparse local de los objetos en 19b1f5e fijó las fuentes y usó únicamente
la identidad histórica del repositorio documentada en README, en modo local-only.
No se consultó GitHub privado ni se cambió el remoto del checkout ECS.

Para regenerar con una copia oficial de esa versión disponible, desde la raíz:

```text
node <archify>/bin/archify.mjs finalize architecture docs/interactive/source/<id>.json docs/interactive/<id>.html --repo-root <fuente-local-del-commit> --quality showcase --out-dir <evidencia-nueva> --json
```

Revisar fuentes/recibos antes de actualizar portfolio/archify-pins.json. No admitir
bytes nuevos cambiando solo el hash. Los recibos locales delivery.json se conservan
ignorados por contener rutas de máquina; no son una instalación ni autorización AWS.

## Regeneración del quinto mapa — 2026-10-23

Archify oficial 3.1.0 regeneró el HTML y pasó validate/deliver/check/browser-check
contra fuente local fijada a 5afa45ee3dd3d2068be42dc4a355444d5658a9c3.
Los otros cuatro originales no cambiaron. GENERATION.json y archify-pins.json
registran el nuevo commit por diagrama y los hashes derivados del recibo real.
La propuesta anterior (PKI/segundo servicio) queda preservada en Git en ese commit,
con hashes registrados, fuera del recorrido público. No se editaron HTML generado
ni metadatos para simular validación. La exclusión es una decisión del propietario,
no una integración completada. El visor integrado volvió a pasar Chrome desktop/
móvil, aislamiento y cero tráfico externo; las capturas nuevas fueron inspeccionadas.
