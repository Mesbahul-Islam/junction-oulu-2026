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
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const jwt = auth && token.get();
  if (jwt) headers.Authorization = `Bearer ${jwt}`;

  const res = await fetch(`${API_URL}/api${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (res.status === 401 && jwt) token.clear(); // expired login: fall back to signed out
  if (!res.ok) throw new ApiError(res.status, data);
  return data;
}

// --- endpoints used by the app -------------------------------------------------

export const login = (email, password) =>
  api("/auth/token/", { method: "POST", body: { email, password }, auth: false });
export const register = (email, password) =>
  api("/accounts/register/", { method: "POST", body: { email, password }, auth: false });
export const getMe = () => api("/accounts/me/");
export const getInterests = () => api("/accounts/interests/");
export const saveOnboarding = (data) => api("/accounts/onboarding/", { method: "POST", body: data });

// Feed cards arrive in the reader's own language (from their profile), with the Finnish original.
export const getFeed = ({ tag, limit = 30 } = {}) =>
  api(`/feed/snippets/?limit=${limit}${tag ? `&tag=${encodeURIComponent(tag)}` : ""}`);
export const getStory = (id) => api(`/feed/snippets/${id}/`);
export const getSaved = () => api("/feed/snippets/bookmarks/");
export const interact = (id, kind) => api(`/feed/snippets/${id}/interact/`, { method: "POST", body: { kind } });
export const reportStory = (id, body) =>
  api(`/feed/snippets/${id}/report/`, { method: "POST", body: { reason: "wrong", body } });
// Newcomer sequence: reviewed stories for the reader's first 48 h / week / month in Finland.
export const getArrival = () => api("/feed/arrival/");
// QR onboarding: /onboarding?code=OULU-WELCOME presets community, language and arrival date.
export const resolveCode = (code) => api(`/accounts/onboarding-link/${encodeURIComponent(code)}/`, { auth: false });

// --- Community News: posts written by members (not journalism; can be flagged) ---------------
export const getCommunityNews = () => api("/communities/news/");
export const getMyCommunities = async () => {
  const data = await api("/communities/groups/");
  return (Array.isArray(data) ? data : data.results || []).filter((g) => g.is_member);
};
export const createPost = (slug, body) => api(`/communities/groups/${slug}/posts/`, { method: "POST", body: { body } });
export const flagPost = (slug, id, reason, note = "") =>
  api(`/communities/groups/${slug}/posts/${id}/flag/`, { method: "POST", body: { reason, note } });
// Tips, questions and topic ideas go to the newsroom (never published automatically).
export const sendContribution = (community, kind, body) =>
  api("/communities/contributions/", { method: "POST", body: { community, kind, body, contributor_consent: true } });
