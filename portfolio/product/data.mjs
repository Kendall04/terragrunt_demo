export const scenarios = {
  nat: {
    title: "Una NAT cae. El sistema responde.",
    label: "NAT A · 6 NOV 2026",
    metric: "2m 29.191s",
    metricLabel: "Despacho → primera confirmación HTTPS",
    note: "Reproducción visual de evidencia histórica. No inicia fallos ni controla AWS. ASG/E13 recupera. Las mediciones proceden del ensayo fechado; la monitorización Sentinel pertenece al archivo histórico.",
    diagram: "ecs-network",
    steps: [
      [
        "17:01:02.357",
        "Interrupción autorizada",
        "Se despacha la sustitución de NAT A. No es el instante físico exacto del corte.",
        "failure",
      ],
      [
        "17:02:01.077",
        "HTTPS falla",
        "La sonda privada registra un fallo dentro del plazo total de 6 segundos.",
        "failure",
      ],
      [
        "17:03:31.549",
        "Egreso recuperado",
        "ASG/E13 repone NAT, EIP, ruta y SDC. La guardia confirma HTTPS con la misma EIP.",
        "success",
      ],
    ],
  },
  sql: {
    title: "Una base activa. Recuperación desde cero.",
    label: "SQL · ENSAYO SUPERVISADO",
    metric: "24m 42.6s",
    metricLabel: "RTO SAME-AZ observado · incluye reboot",
    note: "CROSS-AZ: 41m31.5s incluyendo reparaciones. No es failover automático, SLA ni prueba de RPO cero ante pérdida abrupta. Se conservaron discos y backups.",
    diagram: "ecs-sql-recovery",
    steps: [
      [
        "01",
        "Aislar al escritor",
        "Drenar la API, deshabilitar logins y comprobar READ_ONLY. Inaccesible no significa aislado.",
        "event",
      ],
      [
        "02",
        "Backup final verificado",
        "COPY_ONLY, CHECKSUM, S3 versionado y SSE-KMS; proteger la copia elegida fuera de Lifecycle.",
        "event",
      ],
      [
        "03",
        "Nueva instancia SQL",
        "Aprovisionar una EC2 en la AZ elegida. Comprobar el aislamiento positivo del origen.",
        "event",
      ],
      [
        "04",
        "Restaurar y comprobar",
        "Restore, CHECKDB, hashes, historial EF y TLS estricto. No activar por un simple estado EC2 Healthy.",
        "event",
      ],
      [
        "05",
        "Handoff de mínimos privilegios",
        "Migrador deshabilitado; runtime SELECT/INSERT y lectura de metadata EF.",
        "event",
      ],
      [
        "06",
        "Reactivar y verificar",
        "ECS usa el nuevo SQL. POST/GET y KMS reales comprobaron el servicio recuperado.",
        "success",
      ],
    ],
  },
  backup: {
    title: "Un backup existe cuando se puede verificar.",
    label: "SQL · PRODUCTOR HORARIO",
    metric: "1 hora",
    metricLabel: "Cadencia del timer nativo",
    note: "El 10 nov 2026 se verificó una versión S3 mediante RESTORE VERIFYONLY WITH CHECKSUM. No se repitió un restore completo. No hay monitor Sentinel operativo en ECS.",
    diagram: "ecs-sql-recovery",
    steps: [
      ["01", "Crear la copia", "sql-backup.timer ejecuta el productor local con credenciales separadas del runtime.", "event"],
      ["02", "Comprobar SQL", "COPY_ONLY y CHECKSUM. El proceso verifica el backup antes de publicarlo.", "event"],
      ["03", "Publicar una pareja", "database.bak y manifest.json tienen versiones S3 exactas, SHA-256 y SSE-KMS.", "success"],
      ["04", "Proteger la retención", "Siete días para versiones admitidas; las dos parejas recientes y los restore holds se conservan. La admisión requiere mantenimiento explícito.", "event"],
      ["05", "Verificar recuperabilidad", "VERIFYONLY WITH CHECKSUM verifica la copia. Los ensayos fríos SAME-AZ/CROSS-AZ probaron además restore y CHECKDB.", "success"],
    ],
  },
};
export const facts = [
  ["API real", "POST /text → SQL/KMS → GET /text", "DEMOSTRADO"],
  ["CD DEV", "Merge → CI → ECR → ECS blue/green", "DEMOSTRADO"],
  ["SQL frío", "SAME-AZ y CROSS-AZ desde EC2 nueva", "DEMOSTRADO"],
  ["TLS estricto", "CA DEV definitiva, validated-v2 sin puente temporal", "DEMOSTRADO"],
  ["PROD", "No instalado ni validado como entrega automática", "NO VALIDADO"],
];
