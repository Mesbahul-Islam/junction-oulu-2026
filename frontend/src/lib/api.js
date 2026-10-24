// Thin wrapper around the Django REST API. Every call sends the JWT if we have one.

export const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

const TOKEN_KEY = "oulu-news-token";

export const token = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (value) => localStorage.setItem(TOKEN_KEY, value),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

export class ApiError extends Error {
  constructor(status, data) {
    super(typeof data === "object" && data?.detail ? data.detail : `Request failed (${status})`);
    this.status = status;
    this.data = data;
  }
}

export async function api(path, { method = "GET", body, auth = true } = {}) {
  const headers = { Accept: "application/json" };
  const upload = body instanceof FormData; // photos: the browser sets the multipart header itself
  if (body !== undefined && !upload) headers["Content-Type"] = "application/json";
  const jwt = auth && token.get();
  if (jwt) headers.Authorization = `Bearer ${jwt}`;

  const res = await fetch(`${API_URL}/api${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : upload ? body : JSON.stringify(body),
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (res.status === 401 && jwt) token.clear(); // expired login: fall back to signed out
  if (!res.ok) throw new ApiError(res.status, data);
  return data;
}

// Transport only. Endpoints live per feature in @/features/<name>/api.js:
//   auth · account · feed · communities · shortlist · notes · fantasy
