// Authored geometric diagrams, not Archify outputs or live telemetry.
const NS = "http://www.w3.org/2000/svg";
function node(name, attrs, text) {
  const n = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (text) n.textContent = text;
  return n;
}
export function topology() {
  const svg = node("svg", {
    viewBox: "0 0 1080 330",
    role: "img",
    "aria-labelledby": "system-title system-description",
    class: "system-map",
  });
  svg.append(
    node("title", { id: "system-title" }, "Arquitectura simplificada ECS V2"),
    node(
      "desc",
      { id: "system-description" },
      "Cliente HTTPS, API Gateway, VPC Link y ALB, ECS Fargate, SQL privado con TLS. ECS usa KMS. NAT proporciona salida; ASG/E13 la recupera. El productor SQL publica backups horarios cifrados en S3.",
    ),
  );
  const defs = node("defs", {}),
    arrow = node("marker", {
      id: "flow-arrow",
      viewBox: "0 0 8 8",
      refX: "7",
      refY: "4",
      markerWidth: "5",
      markerHeight: "5",
      orient: "auto",
    });
  arrow.append(
    node("path", {
      d: "M1 1L7 4L1 7",
      fill: "none",
      stroke: "context-stroke",
      "stroke-width": "1.5",
    }),
  );
  defs.append(arrow);
  svg.append(defs);
  svg.append(
    node("rect", {
      x: 355,
      y: 75,
      width: 700,
      height: 135,
      rx: 16,
      class: "map-boundary",
    }),
    node(
      "text",
      { x: 375, y: 100, class: "map-caption" },
      "Subnets privadas · aplicación y datos",
    ),
  );
  const lines = [
    ["M140 153H190", "data"],
    ["M320 153H390", "data"],
    ["M520 153H585", "data"],
    ["M715 153H795", "data"],
    ["M650 118V45H795", "control"],
    ["M650 188V262H520", "egress"],
    ["M865 188V230", "observe"],
      ];
  for (const [d, tone] of lines)
    svg.append(
      node("path", {
        d,
        class: "map-line " + tone,
        "marker-end": "url(#flow-arrow)",
      }),
    );
  const nodes = [
    [20, 118, 120, "Cliente", "HTTPS", "client"],
    [190, 118, 130, "API Gateway", "HTTP API", "edge"],
    [390, 118, 130, "VPC Link / ALB", "HTTP privado", "edge"],
    [585, 118, 130, "ECS Fargate", "API .NET 10", "compute"],
    [795, 118, 150, "SQL Server", "TLS estricto", "database"],
    [795, 10, 150, "KMS", "Encrypt / Decrypt", "kms"],
    [390, 230, 130, "NAT A / B", "ASG + E13", "nat"],
    [795, 230, 150, "Backups S3", "Horario · SSE-KMS", "database"],
  ];
  for (const [x, y, w, title, detail, kind] of nodes) {
    const g = node("g", { class: "map-node " + kind });
    g.append(
      node("rect", { x, y, width: w, height: 70, rx: 10 }),
      node(
        "text",
        { x: x + w / 2, y: y + 29, class: "map-name", "text-anchor": "middle" },
        title,
      ),
      node(
        "text",
        {
          x: x + w / 2,
          y: y + 49,
          class: "map-detail",
          "text-anchor": "middle",
        },
        detail,
      ),
    );
    svg.append(g);
  }
  svg.append(
    node(
      "text",
      { x: 455, y: 321, class: "map-caption", "text-anchor": "middle" },
      "Subnets públicas",
    ),
    node(
      "text",
      { x: 688, y: 293, class: "map-caption", "text-anchor": "middle" },
      "Egreso hacia AWS APIs",
    ),
    node("text", { x: 883, y: 223, class: "map-caption" }, "Evidencia S3"),
  );
  return svg;
}
export function incidentSystem(el, scenario, step) {
  const labels =
    scenario === "nat"
      ? ["Subnet privada", "NAT A", "ASG / E13", "Ruta / EIP", "HTTPS"]
      : scenario === "sql"
        ? [
            "Origen aislado",
            "Backup S3",
            "Nueva EC2",
            "CHECKDB / TLS",
            "API recuperada",
          ]
        : ["Productor SQL", "CHECKSUM", "Backup S3", "Retención", "VERIFYONLY"];
  const states =
    scenario === "nat"
      ? [1, 1, 4]
      : scenario === "sql"
        ? [0, 1, 2, 3, 3, 4]
        : [0, 1, 2, 3, 4];
  return el(
    "div",
    { class: "incident-system", "aria-label": "Relaciones del escenario" },
    labels.map((label, i) =>
      el(
        "div",
        {
          class: "system-stop" + (i === (states[step] ?? 0) ? " engaged" : ""),
        },
        el("span", { class: "system-dot", "aria-hidden": "true" }),
        el("span", {}, label),
      ),
    ),
    el(
      "p",
      { class: "system-caption" },
      scenario === "nat"
        ? "Recuperación independiente: ASG / E13. Medición del ensayo de noviembre."
        : scenario === "sql"
          ? "Recuperación supervisada. Una sola base activa."
          : "El productor y las herramientas SQL verifican la copia; sin Sentinel.",
    ),
  );
}
