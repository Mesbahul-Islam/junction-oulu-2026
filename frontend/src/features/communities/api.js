// Community endpoints. Transport (JWT, errors) lives in @/lib/api.
import { api } from "@/lib/api";

// Community News: posts written by members (not journalism; can be flagged).
export const getCommunityNews = () => api("/communities/news/");
// Cursor-paginated lists hand back an absolute `next` URL; api() wants the path after /api.
export const getPage = (url) => api(url.slice(url.indexOf("/api/") + 4));
// One community's top-level posts, newest first (members only).
export const getGroupPosts = (slug) => api(`/communities/groups/${slug}/posts/`);
export const getCommunities = async () => {
  const data = await api("/communities/groups/");
  return Array.isArray(data) ? data : data.results || [];
};
// Communities matching the reader's profile (situation, topics, place, language), each with `reasons`.
export const getRecommendedCommunities = () => api("/communities/groups/recommended/");
export const joinCommunity = (slug) => api(`/communities/groups/${slug}/join/`, { method: "POST" });
export const leaveCommunity = (slug) => api(`/communities/groups/${slug}/leave/`, { method: "POST" });
// With a photo, faces are blurred on the server as it uploads; a moderator checks it before others see it.
export const createPost = (slug, body, photo) => {
  if (!photo) return api(`/communities/groups/${slug}/posts/`, { method: "POST", body: { body } });
  const form = new FormData();
  form.append("body", body);
  form.append("image", photo);
  return api(`/communities/groups/${slug}/posts/`, { method: "POST", body: form });
};
// Only the post's author may delete it.
export const deletePost = (slug, id) => api(`/communities/groups/${slug}/posts/${id}/`, { method: "DELETE" });
export const likePost = (slug, id, liked) =>
  api(`/communities/groups/${slug}/posts/${id}/like/`, { method: liked ? "POST" : "DELETE" });
export const sharePost = (slug, id) => api(`/communities/groups/${slug}/posts/${id}/share/`, { method: "POST" });
// Replies to a post, oldest first (the whole thread, not paginated).
export const getReplies = (slug, id) => api(`/communities/groups/${slug}/posts/?parent=${id}`);
export const replyToPost = (slug, id, body) =>
  api(`/communities/groups/${slug}/posts/`, { method: "POST", body: { body, parent: id } });
export const getPost = (slug, id) => api(`/communities/groups/${slug}/posts/${id}/`);
export const flagPost = (slug, id, reason, note = "") =>
  api(`/communities/groups/${slug}/posts/${id}/flag/`, { method: "POST", body: { reason, note } });
// Tips, questions and topic ideas go to the newsroom (never published automatically).
export const sendContribution = (community, kind, body) =>
  api("/communities/contributions/", { method: "POST", body: { community, kind, body, contributor_consent: true } });
// The reader's own questions, tips and ideas, newest first, with where each one stands.
export const getContributions = () => api("/communities/contributions/");
