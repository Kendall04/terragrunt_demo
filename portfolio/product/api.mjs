// Public API contract only. No cloud SDK, credentials, retry or fallback.
export const MAX_BYTES = 4096;
export function validText(text) {
  if (typeof text !== "string" || !text.trim())
    throw new Error("Escribe un mensaje.");
  if (new TextEncoder().encode(text).length > MAX_BYTES)
    throw new Error("Máximo 4096 bytes UTF-8.");
  return text;
}
// SQL stores DateTime.UtcNow but EF's unspecified DateTime serializes without Z.
// The existing API's UTC contract must not be reinterpreted in the browser's local zone.
export function utcTimestamp(value) {
  if (
    typeof value !== "string" ||
    !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,7})?(?:Z|[+-]\d\d:\d\d)?$/.test(
      value,
    )
  )
    throw new Error("Timestamp incompatible.");
  return /(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : value + "Z";
}
export function parseText(value) {
  if (
    !value ||
    !Number.isInteger(value.id) ||
    value.id < 1 ||
    typeof value.text !== "string" ||
    typeof value.createdAt !== "string" ||
    !Number.isFinite(Date.parse(value.createdAt))
  )
    throw new Error("Respuesta incompatible con DemoTextDto.");
  return { ...value, createdAt: utcTimestamp(value.createdAt) };
}
export function createDemo() {
  let next = 3;
  let rows = [];
  const reset = () => {
    next = 3;
    rows = [
      {
        id: 2,
        text: "La recuperación se demuestra con evidencia.",
        createdAt: "2026-11-06T17:04:30Z",
      },
      {
        id: 1,
        text: "Hola, ECS. Este mensaje vive solo en esta pestaña.",
        createdAt: "2026-11-06T17:01:02Z",
      },
    ];
  };
  reset();
  return {
    mode: "demo",
    async health() {
      return { live: "Simulado", ready: "Sin dependencias AWS" };
    },
    async create(text) {
      const row = {
        id: next++,
        text: validText(text),
        createdAt: new Date().toISOString(),
      };
      rows.unshift(row);
      return { ...row };
    },
    async list(page = 1, size = 5) {
      return rows.slice((page - 1) * size, page * size).map((x) => ({ ...x }));
    },
    reset,
  };
}
export function createAws(token, request = globalThis.fetch, timeout = 12000) {
  async function call(path, method = "GET", body) {
    if (!token)
      throw new Error(
        "Sesión local bloqueada. Abre el enlace temporal del operador.",
      );
    const abort = new AbortController();
    const timer = setTimeout(() => abort.abort(), timeout);
    try {
      const r = await request("/_api" + path, {
        method,
        headers: {
          "X-ECS-Session": token,
          ...(body ? { "Content-Type": "application/json" } : {}),
        },
        body: body ? JSON.stringify(body) : undefined,
        signal: abort.signal,
        credentials: "omit",
        cache: "no-store",
        redirect: "error",
      });
      if (!r.ok)
        throw new Error(
          `HTTP ${r.status}. ${method === "POST" ? "Resultado de escritura no confirmado: no reintentar automáticamente." : "AWS no disponible; no se usan datos DEMO."}`,
        );
      return await r.json();
    } catch (e) {
      if (e.name === "AbortError")
        throw new Error(
          "Tiempo de espera agotado. Estado AWS desconocido; no se reintentó.",
        );
      throw e;
    } finally {
      clearTimeout(timer);
    }
  }
  return {
    mode: "aws",
    async health() {
      const live = await call("/health/live");
      const ready = await call("/ready");
      if (live.status !== "Healthy" || ready.status !== "Healthy")
        throw new Error("Dependencias AWS no saludables.");
      return { live: live.status, ready: ready.status, checks: ready.checks };
    },
    async create(text) {
      return parseText(await call("/text", "POST", { text: validText(text) }));
    },
    async list(page = 1, size = 5) {
      if (
        !Number.isInteger(page) ||
        page < 1 ||
        page > 20 ||
        ![1, 5, 10].includes(size)
      )
        throw new Error("Paginación fuera del límite local.");
      const rows = await call(`/text?page=${page}&pageSize=${size}`);
      if (!Array.isArray(rows) || rows.length > size)
        throw new Error("Respuesta de página inválida.");
      return rows.map(parseText);
    },
  };
}
