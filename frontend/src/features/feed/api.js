// Feed endpoints. Transport (JWT, errors) lives in @/lib/api.
import { api, API_URL, token } from "@/lib/api";

// Feed cards arrive in the reader's own language (from their profile), with the Finnish original.
export const getFeed = ({ tag, limit = 30, offset = 0 } = {}) =>
  api(`/feed/snippets/?limit=${limit}&offset=${offset}${tag ? `&tag=${encodeURIComponent(tag)}` : ""}`);
export const getStory = (id) => api(`/feed/snippets/${id}/`);
export const getSaved = () => api("/feed/snippets/bookmarks/");
export const interact = (id, kind) => api(`/feed/snippets/${id}/interact/`, { method: "POST", body: { kind } });
// The story read aloud (mp3 blob) in the language of the version shown; null when it has no audio
// (Sámi, no voice key, ElevenLabs down). An mp3, so not through api(), which parses JSON.
export async function getStoryAudio(id, lang) {
  const jwt = token.get();
  const res = await fetch(`${API_URL}/api/feed/snippets/${id}/audio/?lang=${lang}`, {
    headers: jwt ? { Authorization: `Bearer ${jwt}` } : {},
  });
  return res.ok ? res.blob() : null;
}
// reason: wrong | outdated | translation | other
export const reportStory = (id, reason, body) =>
  api(`/feed/snippets/${id}/report/`, { method: "POST", body: { reason, body } });
// Newcomer sequence: reviewed stories for the reader's first 48 h / week / month in Finland.
export const getArrival = () => api("/feed/arrival/");
