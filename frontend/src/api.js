const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function req(method, path, body, isForm = false) {
  const opts = { method, headers: {} };
  if (body) {
    if (isForm) {
      opts.body = body; // FormData
    } else {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
  }
  const res = await fetch(`${BASE}${path}`, opts);
  if (!res.ok) throw new Error(await res.text());
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  entries: {
    list: (params = {}) => {
      const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v != null)).toString();
      return req("GET", `/entries/${qs ? "?" + qs : ""}`);
    },
    get: (id) => req("GET", `/entries/${id}`),
    create: (text, sourceType = "note") => {
      const fd = new FormData();
      fd.append("text", text);
      fd.append("source_type", sourceType);
      return req("POST", "/entries/", fd, true);
    },
    upload: (file, sourceType = "transcript") => {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("source_type", sourceType);
      return req("POST", "/entries/upload", fd, true);
    },
    delete: (id) => req("DELETE", `/entries/${id}`),
  },
  search: (q, limit = 10) => req("GET", `/search/?q=${encodeURIComponent(q)}&limit=${limit}`),
  chat: (messages, top_k = 5) => req("POST", "/chat/", { messages, top_k }),
  entities: {
    list: (params = {}) => {
      const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v != null)).toString();
      return req("GET", `/entities/${qs ? "?" + qs : ""}`);
    },
    get: (id) => req("GET", `/entities/${id}`),
  },
};
