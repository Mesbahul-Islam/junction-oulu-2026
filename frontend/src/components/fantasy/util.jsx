import { useEffect, useState } from "react";

import { API_URL } from "../../lib/api";
import { useT } from "../../lib/lamariText";

export const LAMARI_POSTER = `${API_URL}/media/fantasy/brands/lamari.webp`;

/** Ticks every 30 s so countdowns stay fresh. */
export function useNow() {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 30000); return () => clearInterval(t); }, []);
  return now;
}

export function countdown(iso, now, lang = "en") {
  const ms = new Date(iso) - now;
  if (ms <= 0) return null;
  const h = Math.floor(ms / 3.6e6), m = Math.floor((ms % 3.6e6) / 6e4);
  const [d, hr, mn] = lang === "fi" ? [" pv", " h", " min"] : ["d", "h", "m"];
  return h >= 24 ? `${Math.floor(h / 24)}${d} ${h % 24}${hr}` : `${h}${hr} ${String(m).padStart(2, "0")}${mn}`;
}

export const finnishTime = (iso, locale = "en-GB") =>
  new Date(iso).toLocaleString(locale, { timeZone: "Europe/Helsinki", weekday: "short", day: "numeric", month: "numeric", hour: "2-digit", minute: "2-digit" });

/** The sponsored prize for a leaderboard place, if any. */
export function prizeFor(rank, rewards, period, scope) {
  return rewards.find((r) => r.kind === "rank" && r.period === period && (scope === "oulu" ? r.scope === "community" : r.scope === "global")
    && rank >= r.rank_from && rank <= r.rank_to);
}

export const placeText = (r, t) => (r.rank_from === r.rank_to ? t("placeOne", { n: r.rank_from }) : t("placeRange", { a: r.rank_from, b: r.rank_to }));

export const TIER_EMOJI = { diamond: "💎", gold: "🥇", silver: "🥈", bronze: "🥉" };
export const MEDAL = { 1: "🥇", 2: "🥈", 3: "🥉" };

export function TierBadge({ tier, size = "sm" }) {
  const t = useT();
  if (!tier) return null;
  return <span className={`fx-tier ${tier} ${size}`}><i aria-hidden="true">{TIER_EMOJI[tier]}</i>{t(tier)}</span>;
}

/** Previous / next pagination. */
export function Pager({ page, pages, onPage, label }) {
  const t = useT();
  if (pages <= 1) return null;
  return (
    <div className="fx-pager">
      <button type="button" disabled={page <= 0} onClick={() => onPage(page - 1)}>{t("previous")}</button>
      <span>{label || `${page + 1} / ${pages}`}</span>
      <button type="button" disabled={page >= pages - 1} onClick={() => onPage(page + 1)}>{t("next")}</button>
    </div>
  );
}

/** Labels AI-worded text. Plain text built from the data needs no label. */
export function Wording({ source }) {
  const t = useT();
  return source === "ai" ? <p className="fx-source">{t("aiWording")}</p> : null;
}
