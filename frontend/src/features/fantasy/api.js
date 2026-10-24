// Fantasy Liiga: season-long, free-to-play manager game on real Liiga data (/api/fantasy/).
// Transport (JWT, errors, API_URL) lives in @/lib/api.
import { api } from "@/lib/api";

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
export const makeTransfers = (outIds, inIds) => api("/fantasy/squad/transfers/", { method: "POST", body: { out: outIds, in: inIds } });
export const shakeUp = (maxPoints) => api("/fantasy/squad/transfers/shake-up/", { method: "POST", body: { max_points: maxPoints } });
