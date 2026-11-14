// Backend bilan ishlash: JWT, avtomatik token yangilash, xato matnlari.
const ACCESS = "access";
const REFRESH = "refresh";

export const tokens = {
  get access() {
    return localStorage.getItem(ACCESS);
  },
  get refresh() {
    return localStorage.getItem(REFRESH);
  },
  set(access, refresh) {
    if (access) localStorage.setItem(ACCESS, access);
    if (refresh) localStorage.setItem(REFRESH, refresh);
  },
  clear() {
    localStorage.removeItem(ACCESS);
    localStorage.removeItem(REFRESH);
  },
};

export class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

function errorMessage(data) {
  if (!data) return "Xatolik yuz berdi";
  if (typeof data === "string") return data;
  if (data.detail) return String(data.detail);
  return Object.entries(data)
    .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(" ") : v}`)
    .join("\n");
}

let refreshing = null;
function refreshAccess() {
  if (!tokens.refresh) return Promise.resolve(false);
  if (!refreshing) {
    refreshing = fetch("/api/users/token/refresh/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh: tokens.refresh }),
    })
      .then(async (res) => {
        if (!res.ok) return false;
        const data = await res.json();
        tokens.set(data.access, data.refresh);
        return true;
      })
      .catch(() => false)
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

export async function api(path, { method = "GET", body, query, auth = true, retry = true } = {}) {
  let url = path;
  if (query) {
    const params = new URLSearchParams(
      Object.entries(query).filter(([, v]) => v !== "" && v != null)
    );
    const qs = params.toString();
    if (qs) url += (path.includes("?") ? "&" : "?") + qs;
  }

  const headers = {};
  if (body) headers["Content-Type"] = "application/json";
  if (auth && tokens.access) headers.Authorization = `Bearer ${tokens.access}`;

  const res = await fetch(url, { method, headers, body: body ? JSON.stringify(body) : undefined });

  if (res.status === 401 && auth && tokens.access) {
    if (retry && (await refreshAccess())) {
      return api(path, { method, body, query, auth, retry: false });
    }
    tokens.clear();
    window.dispatchEvent(new Event("auth:logout"));
    return api(path, { method, body, query, auth: false, retry: false });
  }

  const data = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(errorMessage(data), res.status, data);
  return data;
}

// DRF ro'yxatlari sahifalangan ({results: [...]}) yoki oddiy massiv bo'lishi mumkin.
export const results = (data) => (Array.isArray(data) ? data : data?.results ?? []);

// Sahifalangan ro'yxatning hamma sahifasini o'qiydi (?page=1,2,...).
export async function fetchAll(path, query = {}, maxPages = 10) {
  const out = [];
  for (let page = 1; page <= maxPages; page++) {
    const data = await api(path, { query: { ...query, page } });
    if (Array.isArray(data)) return data;
    out.push(...(data?.results ?? []));
    if (!data?.next) break;
  }
  return out;
}
