// Community Notes on posts (like X): read, write, rate. A note shows once members in
// different situations rate it helpful. Transport lives in @/lib/api.
import { api } from "@/lib/api";

export const getPostNotes = (postId) => api(`/notes/notes/?post=${postId}`);
export const writeNote = (postId, note) => api("/notes/notes/", { method: "POST", body: { post: postId, ...note } });
export const rateNote = (id, value, tags) => api(`/notes/notes/${id}/rate/`, { method: "POST", body: { value, tags } });
