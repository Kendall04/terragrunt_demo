import { timingSafeEqual } from "node:crypto";
export const AWS_ENDPOINT =
  "https://4cjyis8dsa.execute-api.us-east-1.amazonaws.com";
export const LAB_END = Date.parse("2026-11-09T04:00:00Z");
export function proxyHandler({
  token,
  expires,
  fetcher = fetch,
  now = Date.now,
  onReceipt = () => {},
}) {
  let calls = 0,
    writes = 0,
    inflight = 0;
  return async (req, res, url, origin) => {
    const reply = (code, message) => {
      res.writeHead(code, {
        "Content-Type": "application/json; charset=utf-8",
        "Cache-Control": "no-store",
      });
      res.end(JSON.stringify({ message }));
    };
    const supplied = String(req.headers["x-ecs-session"] ?? "");
    if (
      !token ||
      !/^[a-f0-9]{64}$/.test(supplied) ||
      supplied.length !== token.length ||
      !timingSafeEqual(Buffer.from(supplied), Buffer.from(token)) ||
      now() >= expires ||
      now() >= LAB_END
    )
      return reply(403, "Session unavailable or expired");
    if (
      (req.headers.origin && req.headers.origin !== origin) ||
      (req.headers["sec-fetch-site"] &&
        !["same-origin", "none"].includes(req.headers["sec-fetch-site"]))
    )
      return reply(403, "Same-origin requests only");
    if (req.method === "POST" && req.headers.origin !== origin)
      return reply(403, "Origin required");
    const route = url.pathname.slice(5);
    let target;
    if (
      req.method === "GET" &&
      ["/health/live", "/ready"].includes(route) &&
      !url.search
    )
      target = route;
    else if (req.method === "GET" && route === "/text") {
      const keys = [...url.searchParams.keys()];
      const page = url.searchParams.get("page"),
        size = url.searchParams.get("pageSize");
      if (
        keys.length !== 2 ||
        new Set(keys).size !== 2 ||
        !/^(?:[1-9]|1[0-9]|20)$/.test(page ?? "") ||
        !["1", "5", "10"].includes(size)
      )
        return reply(400, "Bounded pagination required");
      target = `/text?page=${page}&pageSize=${size}`;
    } else if (req.method === "POST" && route === "/text" && !url.search)
      target = "/text";
    else return reply(404, "Route not exposed");
    if (calls >= 60 || inflight >= 2 || (req.method === "POST" && writes >= 2))
      return reply(429, "Local session request limit");
    let body;
    if (req.method === "POST") {
      if (req.headers["content-type"] !== "application/json")
        return reply(415, "JSON required");
      let bytes = 0;
      const parts = [];
      for await (const chunk of req) {
        bytes += chunk.length;
        if (bytes > 24576) return reply(413, "Body too large");
        parts.push(chunk);
      }
      try {
        const d = JSON.parse(Buffer.concat(parts).toString("utf8"));
        if (
          Object.keys(d).length !== 1 ||
          typeof d.text !== "string" ||
          !d.text.trim() ||
          Buffer.byteLength(d.text) > 4096
        )
          throw new Error();
        body = JSON.stringify({ text: d.text });
      } catch {
        return reply(400, "Invalid text contract");
      }
    }
    // Reading a POST body yields. Recheck atomically before reserving a dispatch.
    if (now() >= expires || now() >= LAB_END)
      return reply(403, "Session unavailable or expired");
    if (calls >= 60 || inflight >= 2 || (req.method === "POST" && writes >= 2))
      return reply(429, "Local session request limit");
    calls++;
    if (body) writes++;
    inflight++;
    const at = new Date(now()).toISOString();
    const start = now();
    let status = 502;
    try {
      const r = await fetcher(AWS_ENDPOINT + target, {
        method: req.method,
        headers: {
          Accept: "application/json",
          ...(body ? { "Content-Type": "application/json" } : {}),
        },
        body,
        redirect: "error",
        signal: AbortSignal.timeout(10000),
      });
      if (!r.headers.get("content-type")?.includes("application/json"))
        throw new Error("Unexpected content type");
      const chunks = [];
      let length = 0;
      for await (const chunk of r.body) {
        length += chunk.length;
        if (length > 131072) throw new Error("Response too large");
        chunks.push(Buffer.from(chunk));
      }
      status = r.status;
      res.writeHead(status, {
        "Content-Type": "application/json; charset=utf-8",
        "Cache-Control": "no-store",
      });
      res.end(Buffer.concat(chunks));
    } catch (e) {
      status = e.name === "TimeoutError" ? 504 : 502;
      reply(status, "AWS request failed; no retry or synthetic fallback");
    } finally {
      inflight--;
      onReceipt({
        at,
        method: req.method,
        path: target,
        status,
        durationMs: now() - start,
      });
    }
  };
}
