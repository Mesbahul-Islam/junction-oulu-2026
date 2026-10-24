// Feed endpoints. Transport (JWT, errors) lives in @/lib/api.
import { api } from "@/lib/api";

// Feed cards arrive in the reader's own language (from their profile), with the Finnish original.
export const getFeed = ({ tag, limit = 30, offset = 0 } = {}) =>
  api(`/feed/snippets/?limit=${limit}&offset=${offset}${tag ? `&tag=${encodeURIComponent(tag)}` : ""}`);
export const getStory = (id) => api(`/feed/snippets/${id}/`);
export const getSaved = () => api("/feed/snippets/bookmarks/");
export const interact = (id, kind) => api(`/feed/snippets/${id}/interact/`, { method: "POST", body: { kind } });
// reason: wrong | outdated | translation | other
export const reportStory = (id, reason, body) =>
  api(`/feed/snippets/${id}/report/`, { method: "POST", body: { reason, body } });
// Newcomer sequence: reviewed stories for the reader's first 48 h / week / month in Finland.
export const getArrival = () => api("/feed/arrival/");
