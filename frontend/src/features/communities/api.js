// Community endpoints. Transport (JWT, errors) lives in @/lib/api.
import { api } from "@/lib/api";

// Community News: posts written by members (not journalism; can be flagged).
export const getCommunityNews = () => api("/communities/news/");
export const getCommunities = async () => {
  const data = await api("/communities/groups/");
  return Array.isArray(data) ? data : data.results || [];
};
export const getMyCommunities = async () => (await getCommunities()).filter((g) => g.is_member);
// Communities matching the reader's profile (situation, topics, place, language), each with `reasons`.
export const getRecommendedCommunities = () => api("/communities/groups/recommended/");
export const joinCommunity = (slug) => api(`/communities/groups/${slug}/join/`, { method: "POST" });
export const leaveCommunity = (slug) => api(`/communities/groups/${slug}/leave/`, { method: "POST" });
export const createPost = (slug, body) => api(`/communities/groups/${slug}/posts/`, { method: "POST", body: { body } });
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
