import { edition } from "./config.mjs";
import { createDemo, createAws, MAX_BYTES } from "./api.mjs";
import { scenarios, facts } from "./data.mjs";
import { atlas } from "./atlas.mjs";
const fragment = new URLSearchParams(location.hash.slice(1)),
  token = fragment.get("session") ?? "";
if (fragment.has("session"))
  history.replaceState(null, "", location.pathname + location.search);
const api = edition === "demo" ? createDemo() : createAws(token);
const main = document.querySelector("main"),
  announce = document.querySelector("#announcer");
let current = "/demo",
  pageNumber = 1,
  busy = false,
  lastCreated = null,
  scenarioTimer = null,
  scenarioIndex = 0,
  scenarioKey = "nat",
  diagramListener = null,
  selectedDiagram = "v2-platform";
const $ = (q) => document.querySelector(q);
function el(tag, attrs = {}, ...children) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else if (k === "class") n.className = v;
    else if (v !== false && v != null) n.setAttribute(k, String(v));
  }
  for (const c of children.flat())
    if (c != null)
      n.append(c instanceof Node ? c : document.createTextNode(String(c)));
  return n;
}
const badge = (text, tone = "") => el("span", { class: "badge " + tone }, text);
const link = (text, href) =>
  el("a", { href, "data-route": "", class: "text-link" }, text, " ↗");
const button = (text, onclick, kind = "", attrs = {}) =>
  el("button", { type: "button", class: kind, onclick, ...attrs }, text);
const heading = (eyebrow, title, desc, extra) =>
  el(
    "div",
    { class: "page-heading" },
    el(
      "div",
      {},
      el("span", { class: "eyebrow" }, eyebrow),
      el("h1", { tabindex: "-1" }, title),
      el("p", {}, desc),
    ),
    extra,
  );
function say(text) {
  announce.textContent = text;
}
function error(target, e) {
  target.replaceChildren(
    el("div", { class: "error", role: "alert" }, e.message),
  );
}
function navigate(url, focus = true) {
  const u = new URL(url, location.origin);
  history.pushState(null, "", u.pathname + u.search);
  render(focus);
}
document.addEventListener("click", (e) => {
  const a = e.target.closest("a[data-route]");
  if (a && !e.metaKey && !e.ctrlKey && !e.shiftKey) {
    e.preventDefault();
    navigate(a.href);
  }
});
addEventListener("popstate", () => render(true));
$("#edition-badge").textContent =
  edition === "aws" ? "AWS · SESIÓN LOCAL" : "DEMO · SINTÉTICO";
$("#edition-badge").className =
  "badge " + (edition === "aws" ? "cyan" : "amber");
$("#edition-note").textContent =
  edition === "aws"
    ? "API real. Acceso local supervisado y temporal. Nunca se sustituye por DEMO."
    : "Solo memoria en esta pestaña. Cero solicitudes AWS. Sin cifrado KMS real.";
$("#global-mode").textContent = $("#edition-badge").textContent;
$("#global-mode").className = $("#edition-badge").className;
$("#footer-mode").textContent =
  edition === "aws"
    ? "AWS DEV · no es una edición pública autenticada"
    : "DEMO independiente · funciona con AWS apagado";
function render(focus = false) {
  if (diagramListener) removeEventListener("message", diagramListener);
  diagramListener = null;
  clearInterval(scenarioTimer);
  scenarioTimer = null;
  current = location.pathname.replace(/\/$/, "") || "/demo";
  main.replaceChildren();
  $("#diagram-nav").replaceChildren();
  document
    .querySelectorAll("[data-route]")
    .forEach((a) =>
      a.classList.toggle("active", new URL(a.href).pathname === current),
    );
  if (current === "/architecture") {
    architecture();
    $("#breadcrumb").textContent = "Architecture / ECS V2";
  } else if (current === "/resilience") {
    resilience();
    $("#breadcrumb").textContent = "Experimentos / Evidencia histórica";
  } else if (current === "/evidence") {
    evidence();
    $("#breadcrumb").textContent = "Evidencia / Alcance y límites";
  } else if (current === "/demo" || current === "/") {
    product();
    $("#breadcrumb").textContent = "Workspace / Texto cifrado";
  } else
    main.append(
      heading(
        "404",
        "Esta vista no existe.",
        "La navegación no cambia de edición.",
      ),
      link("Volver al workspace", "/demo"),
    );
  if (focus) $("h1")?.focus();
}
function product() {
  main.append(
    heading(
      "TEXT WORKSPACE",
      "Tu texto. Un recorrido cloud.",
      edition === "demo"
        ? "Explora cómo una API .NET recibe, cifra, persiste y recupera texto. Aquí todo es sintético."
        : "Conexión explícita a AWS DEV. Solo texto sintético no sensible; los mensajes persisten en SQL.",
      badge(
        edition === "demo" ? "MEMORIA LOCAL" : "AWS REAL",
        edition === "demo" ? "amber" : "cyan",
      ),
    ),
  );
  const stats = el(
    "div",
    { class: "stats" },
    stat("01", "API .NET 10", "ECS Fargate · contrato /text"),
    stat(
      "02",
      "Cifrado + persistencia",
      edition === "demo"
        ? "Representación, sin KMS ni SQL"
        : "KMS y SQL del backend real",
    ),
    stat("03", "Leer y verificar", "El navegador recibe texto descifrado"),
  );
  const health = el(
    "div",
    { id: "health-result", class: "health-strip" },
    badge(
      edition === "demo" ? "SIMULADO" : "SIN COMPROBAR",
      edition === "demo" ? "amber" : "",
    ),
    el(
      "p",
      {},
      edition === "demo"
        ? "La DEMO no mide la salud de AWS."
        : "Conecta para comprobar proceso, SQL y KMS.",
    ),
    button(
      edition === "demo" ? "Cómo funciona" : "Comprobar conexión",
      async () => {
        if (edition === "demo") {
          flow.select(1);
          return;
        }
        const b = health.querySelector("button");
        b.disabled = true;
        try {
          const h = await api.health();
          health.querySelector("p").textContent =
            `Liveness: ${h.live} · Readiness: ${h.ready} · SQL + KMS`;
          health.querySelector(".badge").textContent = "HEALTHY";
          say("Conexión AWS comprobada");
        } catch (e) {
          health.querySelector("p").textContent = e.message;
          health.querySelector(".badge").textContent = "OFFLINE / ERROR";
        } finally {
          b.disabled = false;
        }
      },
      "quiet",
    ),
  );
  const notice = el("div", { id: "request-status" }),
    input = el("textarea", {
      id: "message",
      rows: "4",
      placeholder: "Una idea pequeña. Una plataforma completa.",
      required: "",
      maxlength: "4096",
    }),
    count = el("span", { class: "counter" }, "0 / 4096 bytes");
  input.addEventListener(
    "input",
    () =>
      (count.textContent = `${new TextEncoder().encode(input.value).length} / ${MAX_BYTES} bytes`),
  );
  const submit = el(
    "button",
    { type: "submit", class: "primary", id: "send" },
    edition === "demo" ? "Crear mensaje sintético →" : "Guardar en AWS →",
  );
  const form = el(
    "form",
    {
      id: "message-form",
      onsubmit: async (e) => {
        e.preventDefault();
        if (busy) return;
        busy = true;
        submit.disabled = true;
        notice.replaceChildren();
        flow.select(1);
        try {
          lastCreated = await api.create(input.value);
          flow.select(2);
          notice.append(
            el(
              "div",
              { class: "success", role: "status" },
              `Mensaje #${lastCreated.id} creado. ${edition === "demo" ? "Solo memoria local." : "POST real confirmado; usa Consultar para verificar persistencia."}`,
            ),
          );
          input.value = "";
          count.textContent = "0 / 4096 bytes";
          pageNumber = 1;
          if (edition === "demo") await load();
          say("Mensaje creado");
        } catch (e) {
          error(notice, e);
        } finally {
          busy = false;
          submit.disabled = false;
        }
      },
    },
    el("label", { for: "message" }, "Mensaje"),
    input,
    el("div", { class: "form-bottom" }, count, submit),
    el(
      "p",
      { class: "fine" },
      edition === "demo"
        ? "No se envía ni se cifra. Recargar restaura los ejemplos."
        : "No incluyas datos personales. El proxy permite como máximo dos escrituras por sesión.",
    ),
  );
  const list = el("div", { id: "messages", class: "message-list" }),
    listStatus = el("div", { id: "list-status" }),
    pageLabel = el("span", { id: "page-label" }, "Página 1");
  async function load() {
    const loadButton = $("#refresh");
    if (loadButton) loadButton.disabled = true;
    listStatus.textContent = "Consultando…";
    try {
      const rows = await api.list(pageNumber, 5);
      list.replaceChildren();
      if (!rows.length)
        list.append(
          el("div", { class: "empty" }, "No hay mensajes en esta página."),
        );
      for (const row of rows) {
        list.append(
          el(
            "article",
            { class: "message-row", "data-id": row.id },
            el(
              "div",
              { class: "message-meta" },
              badge(`#${row.id}`),
              el(
                "time",
                {},
                new Date(row.createdAt)
                  .toISOString()
                  .replace("T", " ")
                  .slice(0, 19) + " UTC",
              ),
              lastCreated?.id === row.id ? badge("ESTA SESIÓN", "green") : null,
            ),
            el("p", {}, row.text),
          ),
        );
      }
      pageLabel.textContent = "Página " + pageNumber;
      listStatus.textContent =
        edition === "demo"
          ? "Datos sintéticos en memoria."
          : `GET real: ${rows.length} registros. No se expone ciphertext.`;
      flow.select(3);
      say("Página consultada");
    } catch (e) {
      list.replaceChildren();
      error(listStatus, e);
    } finally {
      if (loadButton) loadButton.disabled = false;
    }
  }
  const flow = flowPanel();
  main.append(
    stats,
    health,
    el(
      "div",
      { class: "workspace-grid" },
      el(
        "section",
        { class: "panel composer" },
        el(
          "div",
          { class: "panel-title" },
          el("h2", {}, "Escribe algo que importe"),
          badge(edition === "demo" ? "DEMO" : "POST /text"),
        ),
        form,
        notice,
      ),
      flow.node,
    ),
    el(
      "section",
      { class: "panel" },
      el(
        "div",
        { class: "panel-title" },
        el(
          "div",
          {},
          el("h2", {}, "Mensajes recuperados"),
          el("p", {}, "Más recientes primero · páginas de cinco"),
        ),
        el(
          "div",
          { class: "actions" },
          edition === "demo"
            ? button(
                "Reiniciar",
                () => {
                  api.reset();
                  notice.replaceChildren();
                  lastCreated = null;
                  pageNumber = 1;
                  load();
                  say("Datos sintéticos reiniciados");
                },
                "quiet",
                { id: "reset" },
              )
            : null,
          button("Consultar ↻", load, "quiet", { id: "refresh" }),
        ),
      ),
      listStatus,
      list,
      el(
        "div",
        { class: "pagination" },
        button(
          "← Anterior",
          () => {
            if (pageNumber > 1) {
              pageNumber--;
              load();
            }
          },
          "quiet",
        ),
        pageLabel,
        button(
          "Siguiente →",
          () => {
            if (pageNumber < 20) {
              pageNumber++;
              load();
            }
          },
          "quiet",
        ),
      ),
    ),
    el(
      "div",
      { class: "callout" },
      el(
        "div",
        {},
        el("h3", {}, "La resiliencia también forma parte del producto."),
        el(
          "p",
          {},
          "Reproduce visualmente incidentes reales de NAT, backups y recuperación SQL.",
        ),
      ),
      link("Explorar resiliencia", "/resilience"),
    ),
  );
  if (edition === "demo") load();
  else
    list.append(
      el(
        "div",
        { class: "empty" },
        "AWS no se consulta automáticamente. Comprueba conexión y solicita la página explícitamente.",
      ),
    );
}
function stat(n, title, desc) {
  return el(
    "article",
    { class: "stat" },
    el("span", { class: "stat-index" }, n),
    el("strong", {}, title),
    el("p", {}, desc),
  );
}
function flowPanel() {
  const details = [
    "HTTP API → VPC Link → ALB → ECS. El backend recibe texto; la API DEV no autentica usuarios.",
    "La aplicación solicita Encrypt a KMS. En DEMO solo representamos el paso: no fabricamos ciphertext.",
    "SQL persiste ciphertext del backend. Un POST exitoso no permite al navegador inspeccionar el disco ni la base.",
    "GET pagina registros, el backend llama Decrypt y devuelve texto. El navegador comprueba ID y contenido.",
  ];
  const detail = el("p", { id: "flow-detail" }, details[0]);
  const buttons = ["Recibir", "Cifrar", "Persistir", "Recuperar"].map(
    (name, i) =>
      button(
        `${String(i + 1).padStart(2, "0")}  ${name}`,
        () => select(i),
        "flow-step",
        { "aria-pressed": i === 0 },
      ),
  );
  function select(i) {
    buttons.forEach((b, j) => {
      b.classList.toggle("selected", j === i);
      b.setAttribute("aria-pressed", String(j === i));
    });
    detail.textContent = details[i];
  }
  return {
    select,
    node: el(
      "section",
      { class: "panel flow-panel" },
      el(
        "div",
        { class: "panel-title" },
        el("h2", {}, "Dentro del recorrido"),
        badge("EXPLICACIÓN"),
      ),
      el("div", { class: "flow" }, buttons),
      detail,
      link("Ver arquitectura", "/architecture?diagram=v2-platform"),
    ),
  };
}
function resilience() {
  const s = scenarios[scenarioKey];
  main.append(
    heading(
      "RESILIENCE LAB",
      "El fallo también tiene una historia.",
      "Recorridos interactivos basados en ensayos documentados. Ningún control de esta vista ejecuta acciones AWS.",
      badge("REPLAY VISUAL", "amber"),
    ),
  );
  const tabs = el(
    "div",
    { class: "tabs", role: "group", "aria-label": "Escenarios" },
    Object.entries(scenarios).map(([key, x]) =>
      button(
        key === "nat"
          ? "NAT / E13"
          : key === "sql"
            ? "SQL recovery"
            : "Backup / Sentinel",
        () => {
          scenarioKey = key;
          scenarioIndex = 0;
          render();
        },
        key === scenarioKey ? "selected" : "",
        { "aria-pressed": key === scenarioKey },
      ),
    ),
  );
  const timeline = el("ol", { class: "timeline" }),
    detail = el("div", { class: "incident-detail" }),
    progress = el("progress", {
      max: s.steps.length - 1,
      value: scenarioIndex,
      "aria-label": "Paso del recorrido",
    }),
    play = button(
      "Reproducir",
      () => {
        if (scenarioTimer) {
          clearInterval(scenarioTimer);
          scenarioTimer = null;
          play.textContent = "Reproducir";
          return;
        }
        if (scenarioIndex === s.steps.length - 1) scenarioIndex = 0;
        play.textContent = "Pausar";
        scenarioTimer = setInterval(() => {
          scenarioIndex++;
          draw();
          if (scenarioIndex === s.steps.length - 1) {
            clearInterval(scenarioTimer);
            scenarioTimer = null;
            play.textContent = "Reproducir";
          }
        }, 2200);
      },
      "primary",
    );
  function draw() {
    timeline.replaceChildren(
      ...s.steps.map(([at, title, , tone], i) =>
        el(
          "li",
          {
            class:
              (i === scenarioIndex ? "current " : "") +
              (i < scenarioIndex ? "done " : "") +
              "tone-" +
              tone,
          },
          button(
            "",
            () => {
              scenarioIndex = i;
              draw();
            },
            "timeline-button",
            {
              "aria-label": title,
              "aria-current": i === scenarioIndex ? "step" : false,
            },
          ),
          el("span", {}, el("time", {}, at), el("strong", {}, title)),
        ),
      ),
    );
    timeline
      .querySelectorAll("button")
      .forEach((b, i) => b.append(String(i + 1)));
    const [at, title, copy, tone] = s.steps[scenarioIndex];
    detail.replaceChildren(
      badge(
        tone === "unknown"
          ? "UNKNOWN · INFORMACIÓN INSUFICIENTE"
          : tone === "failure"
            ? "INCIDENTE"
            : tone === "success"
              ? "EVIDENCIA DE RECUPERACIÓN"
              : "CONTROL / EVALUACIÓN",
        tone === "success" ? "green" : "amber",
      ),
      el("span", { class: "incident-time" }, at),
      el("h2", {}, title),
      el("p", {}, copy),
      el(
        "div",
        { class: "incident-signal" },
        el("span", {}, "01  INFRAESTRUCTURA"),
        el("i", {}),
        el("span", {}, "02  OBSERVACIÓN"),
        el("i", {}),
        el("span", {}, "03  EVIDENCIA"),
      ),
    );
    progress.value = scenarioIndex;
  }
  main.append(
    tabs,
    el(
      "section",
      { class: "panel scenario-head" },
      el(
        "div",
        {},
        el("span", { class: "eyebrow" }, s.label),
        el("h2", {}, s.title),
        el("p", {}, s.note),
      ),
      el(
        "div",
        { class: "metric" },
        el("strong", {}, s.metric),
        el("span", {}, s.metricLabel),
      ),
    ),
    el(
      "div",
      { class: "scenario-grid" },
      el("section", { class: "panel timeline-panel" }, timeline),
      el(
        "section",
        { class: "panel scenario-stage" },
        detail,
        progress,
        el(
          "div",
          { class: "actions" },
          play,
          button(
            "Paso siguiente",
            () => {
              scenarioIndex = Math.min(s.steps.length - 1, scenarioIndex + 1);
              draw();
            },
            "quiet",
          ),
          button(
            "Reiniciar",
            () => {
              clearInterval(scenarioTimer);
              scenarioTimer = null;
              scenarioIndex = 0;
              play.textContent = "Reproducir";
              draw();
            },
            "quiet",
          ),
        ),
      ),
    ),
    link(
      "Explorar el diagrama y sus fuentes",
      "/architecture?diagram=" + s.diagram,
    ),
  );
  draw();
}
function architecture() {
  const requested = new URLSearchParams(location.search).get("diagram");
  selectedDiagram = atlas.some((x) => x.id === requested)
    ? requested
    : "v2-platform";
  const d = atlas.find((x) => x.id === selectedDiagram);
  $("#diagram-nav").append(
    el("p", { class: "nav-caption" }, "ATLAS ECS V2"),
    ...atlas
      .filter((x) => !x.historical)
      .map((x) =>
        el(
          "a",
          {
            href: "/architecture?diagram=" + x.id,
            "data-route": "",
            class: x.id === d.id ? "selected" : "",
          },
          x.label,
        ),
      ),
    el(
      "details",
      {},
      el("summary", {}, "Historia · V1 y ensayos"),
      ...atlas
        .filter((x) => x.historical)
        .map((x) =>
          el(
            "a",
            { href: "/architecture?diagram=" + x.id, "data-route": "" },
            x.label,
          ),
        ),
    ),
  );
  main.append(
    heading(
      "ARCHITECTURE EXPLORER",
      d.title,
      d.description,
      badge(
        d.historical ? "HISTÓRICO" : "ATLAS V2",
        d.historical ? "amber" : "cyan",
      ),
    ),
  );
  const selector = el(
    "select",
    {
      id: "diagram-select",
      "aria-label": "Elegir diagrama",
      onchange: (e) => navigate("/architecture?diagram=" + e.target.value),
    },
    atlas.map((x) =>
      el(
        "option",
        { value: x.id, selected: x.id === d.id },
        (x.historical ? "HISTÓRICO · " : "V2 · ") + x.label,
      ),
    ),
  );
  const frame = el("iframe", {
      id: "diagram-frame",
      src: "/diagrams/" + d.id + ".html",
      title: d.title,
      sandbox: "allow-scripts",
      referrerpolicy: "no-referrer",
      loading: "eager",
    }),
    canvas = el("section", { class: "diagram-stage" }, frame);
  main.append(
    el(
      "div",
      { class: "diagram-toolbar" },
      selector,
      el("span", {}, "Archify 3.1.0 · fuente fijada · sin telemetría"),
      !d.historical
        ? button(
            "Hoja de lectura",
            (e) => {
              const reading = frame.getAttribute("src").startsWith("/reading/");
              frame.src =
                (reading ? "/diagrams/" : "/reading/") + d.id + ".html";
              e.currentTarget.textContent = reading
                ? "Hoja de lectura"
                : "Volver al visor";
            },
            "quiet",
          )
        : null,
      button(
        "Ampliar espacio ↗",
        () => {
          canvas.classList.toggle("expanded");
        },
        "quiet",
      ),
    ),
    canvas,
    el(
      "p",
      { class: "fine" },
      "Usa + / − y ajustar dentro del diagrama; arrastra para recorrerlo. En móvil, amplía una zona o utiliza la alternativa textual.",
    ),
    el(
      "div",
      { class: "legend" },
      [
        "IMPLEMENTADO",
        "DESPLEGADO",
        "DEMOSTRADO",
        "HISTÓRICO",
        "NO VALIDADO",
      ].map((x) => badge(x)),
    ),
    el(
      "div",
      { class: "callout" },
      el(
        "p",
        {},
        "Snapshot y evidencias fechadas en noviembre de 2026. La recuperación SQL es supervisada. La continuidad de 12–24 h tiene seguimiento independiente.",
      ),
      el(
        "a",
        { href: "/sources/" + d.id + ".json", download: d.id + ".json" },
        "Fuente JSON ↓",
      ),
    ),
  );
  const inspector = el("section", {
      class: "panel inspector",
      id: "node-inspector",
    }),
    nodes = el(
      "div",
      { class: "node-list" },
      d.nodes.map((n) =>
        button(n.name, () => inspect(n), "quiet", { "data-inspect": n.id }),
      ),
    );
  function inspect(n) {
    inspector.replaceChildren(
      el("span", { class: "eyebrow" }, "COMPONENTE / EVIDENCIA"),
      el("h2", {}, n.name),
      el("p", {}, n.detail),
      el(
        "div",
        { class: "legend" },
        n.status.map((x) =>
          badge(typeof x === "string" ? x : JSON.stringify(x)),
        ),
      ),
      el(
        "div",
        { class: "source-links" },
        n.sources.map((s) =>
          el(
            "a",
            { href: s.url, target: "_blank", rel: "noopener noreferrer" },
            s.path + ":" + s.line + " ↗",
          ),
        ),
      ),
    );
  }
  const relations = el(
    "details",
    { class: "panel textual" },
    el("summary", {}, "Alternativa textual · componentes y relaciones"),
    nodes,
    el(
      "ul",
      {},
      d.relations.map((r) =>
        el(
          "li",
          {},
          `${d.nodes.find((x) => x.id === r.from)?.name ?? r.from} → ${d.nodes.find((x) => x.id === r.to)?.name ?? r.to}: ${r.label}`,
        ),
      ),
    ),
  );
  main.append(
    el("div", { class: "architecture-details" }, relations, inspector),
    el("p", { class: "fine mono" }, "SHA256 original: " + d.sha256),
  );
  inspect(d.nodes[0]);
  frame.addEventListener("load", () => say("Diagrama cargado"));
  const listener = (e) => {
    if (current !== "/architecture" || !frame.isConnected) {
      removeEventListener("message", listener);
      return;
    }
    if (
      e.source !== frame.contentWindow ||
      e.origin !== "null" ||
      e.data?.type !== "ecs-diagram-node"
    )
      return;
    const n = d.nodes.find((x) => x.id === e.data.id);
    if (n) inspect(n);
  };
  addEventListener("message", listener);
  diagramListener = listener;
}
function evidence() {
  main.append(
    heading(
      "EVIDENCE, NOT ASSUMPTIONS",
      "Qué está demostrado. Y qué no.",
      "Cada resultado tiene un contexto, una fecha y un límite. Esta web no es un dashboard de AWS.",
      badge("EVIDENCIA HISTÓRICA"),
    ),
    el(
      "div",
      { class: "evidence-grid" },
      facts.map(([title, copy, state]) =>
        el(
          "article",
          { class: "panel evidence-card" },
          badge(state, state === "DEMOSTRADO" ? "green" : "amber"),
          el("h2", {}, title),
          el("p", {}, copy),
        ),
      ),
    ),
    el(
      "section",
      { class: "panel reading" },
      el("h2", {}, "Tres planos, sin confusiones"),
      el(
        "p",
        {},
        "DEMO usa datos sintéticos en memoria y nunca solicita AWS. AWS Edition llama a la API real mediante una sesión local explícita. Architecture Explorer muestra código y evidencia fechados; no mide la salud actual.",
      ),
      el("h3", {}, "Límites aceptados del laboratorio"),
      el(
        "ul",
        {},
        [
          "API DEV pública sin autenticación: no se publica una edición AWS de lectura/escritura.",
          "Una tarea blue y un SQL activo: recuperación fría; no redundancia permanente de aplicación/base.",
          "TLS termina en API Gateway; HTTP dentro de la VPC. SQL valida TLS con confianza de laboratorio.",
          "Un correo de resolución NAT no demuestra un correo de caída. Unknown no significa Healthy.",
          "S3 versionado y SSE-KMS no equivalen a Object Lock. Lifecycle es asíncrono.",
        ].map((x) => el("li", {}, x)),
      ),
      link("Revisar trust boundaries", "/architecture?diagram=v2-trust"),
      el("h3", {}, "Fuentes mantenidas en el repositorio"),
      el(
        "div",
        { class: "source-links" },
        [
          "DEV-V2-20261105.md",
          "SENTINEL-CHAOS-20261106.md",
          "V2-RECOVERY-SECURITY-20261105.md",
          "interactive/V2-AUDIT.md",
        ].map((p) =>
          el(
            "a",
            {
              href:
                "https://github.com/Kendall04/terragrunt_demo/blob/a46636d6b0b9f38bdbe2512f54cb75d99b406e8d/docs/" +
                p,
              target: "_blank",
              rel: "noopener noreferrer",
            },
            p + " ↗",
          ),
        ),
      ),
    ),
  );
}
render();
