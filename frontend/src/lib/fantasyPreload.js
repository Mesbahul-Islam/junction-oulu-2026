import { getFantasyPlayers, getFantasySeason, getLeagues, getMySquad, getRewards } from "./api";

// Sports data is kept on the device with a time limit per kind, so reopening or refreshing the
// app shows it instantly; only what is out of date is fetched again, in the background.

const PREFIX = "lamari:";
export const TTL = { season: 30 * 60e3, players: 6 * 3600e3, rewards: 6 * 3600e3, squad: 2 * 60e3, leagues: 2 * 60e3 };

function read(key) {
  try { return JSON.parse(localStorage.getItem(PREFIX + key)); } catch { return null; }
}
function write(key, data) {
  try { localStorage.setItem(PREFIX + key, JSON.stringify({ at: Date.now(), data })); } catch { /* storage full or private mode */ }
}

const inflight = {};

/** Stored copy now (or undefined), plus a promise for fresh data when the copy is older than `ttl`. */
export function cached(key, fetcher, ttl) {
  const hit = read(key);
  const fresh = hit && Date.now() - hit.at < ttl;
  let promise = Promise.resolve(hit?.data);
  if (!fresh) {
    inflight[key] ||= fetcher().then((data) => { write(key, data); return data; }).finally(() => { delete inflight[key]; });
    promise = inflight[key];
  }
  return { stale: hit?.data, promise };
}

export const forget = (key) => { try { localStorage.removeItem(PREFIX + key); } catch { /* ignore */ } };

export function loadFantasy() {
  return {
    season: cached("season", getFantasySeason, TTL.season),
    players: cached("players", getFantasyPlayers, TTL.players),
    rewards: cached("rewards", getRewards, TTL.rewards),
    squad: cached("squad", () => getMySquad().catch((e) => (e.status === 404 ? null : Promise.reject(e))), TTL.squad),
    leagues: cached("leagues", () => getLeagues().catch(() => []), TTL.leagues),
  };
}

const warmed = new Set();

/** Fetch photos into the browser cache a few at a time while the page is idle. */
export function warmPhotos(urls, batch = 12) {
  const queue = urls.filter((u) => u && !warmed.has(u));
  queue.forEach((u) => warmed.add(u));
  const idle = window.requestIdleCallback || ((fn) => setTimeout(fn, 50));
  const next = () => {
    const chunk = queue.splice(0, batch);
    if (!chunk.length) return;
    Promise.all(chunk.map((u) => new Promise((done) => { const img = new Image(); img.onload = img.onerror = done; img.src = u; })))
      .then(() => idle(next));
  };
  idle(next);
}

export const photoOf = (p) => p.photo_url || p.picture_url;

/** From Profile: refresh what's stale, then warm your squad's photos first and everyone else's after. */
export function preloadFantasy() {
  const c = loadFantasy();
  Promise.all([c.players.promise, c.squad.promise]).then(([players, squad]) => {
    const mineFirst = [...(squad?.players || []), ...[...(players || [])].sort((a, b) => b.total_points - a.total_points)];
    warmPhotos(mineFirst.map(photoOf));
  }).catch(() => {});
}
