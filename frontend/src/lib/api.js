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
export const register = (email, username, password) =>
  api("/accounts/register/", { method: "POST", body: { email, username, password }, auth: false });
export const updateMe = (data) => api("/accounts/me/", { method: "PATCH", body: data });
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
// "What should we cover next?": stories members vote on; votes count in the newsroom's next pick.
export const getShortlist = () => api("/agents/shortlist/");
export const voteStory = (id, on) => api(`/agents/shortlist/${id}/vote/`, { method: on ? "POST" : "DELETE" });
// QR onboarding: /onboarding?code=OULU-WELCOME presets community, language and arrival date.
export const resolveCode = (code) => api(`/accounts/onboarding-link/${encodeURIComponent(code)}/`, { auth: false });

// --- Community News: posts written by members (not journalism; can be flagged) ---------------
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
// Community Notes on posts (like X): read, write, rate. A note shows once members in different
// situations rate it helpful.
export const getPostNotes = (postId) => api(`/notes/notes/?post=${postId}`);
export const writeNote = (postId, note) => api("/notes/notes/", { method: "POST", body: { post: postId, ...note } });
export const rateNote = (id, value, tags) => api(`/notes/notes/${id}/rate/`, { method: "POST", body: { value, tags } });
export const getPost = (slug, id) => api(`/communities/groups/${slug}/posts/${id}/`);
export const flagPost = (slug, id, reason, note = "") =>
  api(`/communities/groups/${slug}/posts/${id}/flag/`, { method: "POST", body: { reason, note } });
// Tips, questions and topic ideas go to the newsroom (never published automatically).
export const sendContribution = (community, kind, body) =>
  api("/communities/contributions/", { method: "POST", body: { community, kind, body, contributor_consent: true } });

// --- Fantasy Liiga: season-long, free-to-play manager game on real Liiga data (/api/fantasy/) ---
export const getFantasySeason = () => api("/fantasy/season/");
export const getFantasyTeams = () => api("/fantasy/teams/");
export const getFixtures = (gameweek) => api(`/fantasy/fixtures/?gameweek=${gameweek}`);
// Every active player in one go (~500), so the squad builder can filter instantly.
export const getFantasyPlayers = async (params = {}) => {
  const q = new URLSearchParams({ limit: 1000, active: "true", ...params });
  return (await api(`/fantasy/players/?${q}`)).results;
};
export const getMySquad = () => api("/fantasy/squad/");
export const createSquad = (name, playerIds) =>
  api("/fantasy/squad/", { method: "POST", body: { name, player_ids: playerIds } });
export const getLineup = () => api("/fantasy/squad/lineup/");
export const setLineup = (lineup) => api("/fantasy/squad/lineup/", { method: "PUT", body: lineup });
export const getSquadHistory = () => api("/fantasy/squad/history/");
export const getLeaderboard = (params = {}) => api(`/fantasy/leaderboard/?${new URLSearchParams(params)}`);
export const getLeagues = () => api("/fantasy/leagues/");
export const createLeague = (name) => api("/fantasy/leagues/", { method: "POST", body: { name } });
export const joinLeague = (code) => api("/fantasy/leagues/join/", { method: "POST", body: { code } });
export const inviteToLeague = (id, username) =>
  api(`/fantasy/leagues/${id}/invite/`, { method: "POST", body: { username } });
// Managers (by @username prefix) who have a team this season: for inviting friends.
export const searchManagers = (q) => api(`/fantasy/managers/?q=${encodeURIComponent(q)}`);
export const getRewards = () => api("/fantasy/rewards/");
export const getVouchers = () => api("/fantasy/vouchers/");
export const getCoach = () => api("/fantasy/squad/coach/");
export const getSquadNews = (offset = 0, limit = 5) => api(`/fantasy/squad/news/?offset=${offset}&limit=${limit}`);
export const getAnalysis = (fixtureId, detail = "short", reader = "fan") =>
  api(`/fantasy/fixtures/${fixtureId}/analysis/?detail=${detail}&reader=${reader}`);
export const askLamari = (message) => api("/fantasy/chat/", { method: "POST", body: { message } });
