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
    update: (id, data) => req("PATCH", `/entries/${id}`, data),
    delete: (id) => req("DELETE", `/entries/${id}`),
  },
  search: (q, limit = 10) => req("GET", `/search/?q=${encodeURIComponent(q)}&limit=${limit}`),
  chat: (messages, top_k = 5) => req("POST", "/chat/", { messages, top_k }),
  home: {
    digest: () => req("GET", "/home/digest"),
    activity: () => req("GET", "/home/activity"),
    suggestions: () => req("GET", "/home/suggestions"),
  },
  rss: {
    status: () => req("GET", "/rss/status"),
    poll: () => req("POST", "/rss/poll"),
    digestLatest: () => req("GET", "/rss/digest/latest"),
    digestGenerate: (date) => req("POST", `/rss/digest/generate${date ? "?date_str=" + date : ""}`),
  },
  entities: {
    list: (params = {}) => {
      const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v != null)).toString();
      return req("GET", `/entities/${qs ? "?" + qs : ""}`);
    },
    get: (id) => req("GET", `/entities/${id}`),
    create: (data) => req("POST", "/entities/", data),
    update: (id, data) => req("PATCH", `/entities/${id}`, data),
    delete: (id) => req("DELETE", `/entities/${id}`),
    addRelationship: (id, data) => req("POST", `/entities/${id}/relationships`, data),
    deleteRelationship: (id) => req("DELETE", `/entities/relationships/${id}`),
    linkEntry: (entryId, data) => req("POST", `/entities/entries/${entryId}/entities`, data),
    unlinkEntry: (linkId) => req("DELETE", `/entities/entry-entity-links/${linkId}`),
  },
  pipeline: {
    opportunities: (params = {}) => {
      const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v != null)).toString();
      return req("GET", `/pipeline/opportunities${qs ? "?" + qs : ""}`);
    },
    accounts: (params = {}) => {
      const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v != null)).toString();
      return req("GET", `/pipeline/accounts${qs ? "?" + qs : ""}`);
    },
    reps: () => req("GET", "/pipeline/reps"),
    byRep: (rep) => req("GET", `/pipeline/by-rep/${encodeURIComponent(rep)}`),
    weeklyActivity: (params = {}) => {
      const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v != null)).toString();
      return req("GET", `/pipeline/weekly-activity${qs ? "?" + qs : ""}`);
    },
  },
};
