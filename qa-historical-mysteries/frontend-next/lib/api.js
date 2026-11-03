// Small fetch helpers. Every call goes through the Next.js rewrite: /api/... -> FastAPI.

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

function failure(res, data) {
  if (res.status === 401 && typeof window !== "undefined") window.dispatchEvent(new Event("session-expired"));
  return new ApiError((data && (data.detail || data.error)) || "Server error", res.status);
}

export async function api(path, { method = "GET", body, signal } = {}) {
  const res = await fetch(`/api${path}`, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal,
  });
  let data = null;
  if ((res.headers.get("content-type") || "").includes("application/json")) {
    try {
      data = await res.json();
    } catch (e) {
      data = null;
    }
  }
  if (!res.ok) throw failure(res, data);
  return data;
}

export async function apiBlob(path, body) {
  const res = await fetch(`/api${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let data = null;
    try {
      data = await res.json();
    } catch (e) {
      data = null;
    }
    throw failure(res, data);
  }
  return res.blob();
}

// ---- Server-Sent Events (the answer appears word by word)
export function parseSse(block) {
  let name = "message";
  const data = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) name = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).trim());
  }
  if (!data.length) return null;
  try {
    return { name, data: JSON.parse(data.join("\n")) };
  } catch (e) {
    return null;
  }
}

export async function askStream(payload, { onMeta, onToken, signal } = {}) {
  const res = await fetch("/api/ask/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  if (!res.ok || !res.body) {
    let data = null;
    try {
      data = await res.json();
    } catch (e) {
      data = null;
    }
    throw failure(res, data);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let done = null;
  for (;;) {
    const { value, done: finished } = await reader.read();
    if (finished) break;
    buffer += decoder.decode(value, { stream: true });
    let cut;
    while ((cut = buffer.indexOf("\n\n")) !== -1) {
      const ev = parseSse(buffer.slice(0, cut));
      buffer = buffer.slice(cut + 2);
      if (!ev) continue;
      if (ev.name === "meta") onMeta?.(ev.data);
      else if (ev.name === "token") onToken?.(ev.data.t);
      else if (ev.name === "done") done = ev.data;
      else if (ev.name === "error") throw new ApiError(ev.data.detail || "Server error", 502);
    }
  }
  if (!done) throw new ApiError("The answer stream ended unexpectedly.", 502);
  return done;
}

// Streams when possible; if the stream cannot even start (proxy buffering, old browser), asks normally.
export async function ask(payload, handlers = {}) {
  let started = false;
  try {
    return await askStream(payload, {
      ...handlers,
      onToken: (t) => {
        started = true;
        handlers.onToken?.(t);
      },
    });
  } catch (e) {
    if (started || e instanceof ApiError) throw e;
    return api("/ask", { method: "POST", body: payload });
  }
}
