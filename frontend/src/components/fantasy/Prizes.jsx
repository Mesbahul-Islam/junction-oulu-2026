import { Ticket } from "lucide-react";
import { useEffect, useState } from "react";

import { getSquadHistory, getVouchers } from "../../lib/api";
import { useT } from "../../lib/lamariText";
import { Spinner } from "../Spinner";
import { PlayerToken } from "./Rink";
import { countdown, Pager, placeText, TierBadge, TierIcon, useNow } from "./util";

const VOUCHER_PAGE = 4;
const TIER_ORDER = ["bronze", "silver", "gold", "diamond"];

/** Where you stand on one prize, in a few words. */
function Status({ reward, squad, bestWeek, standing }) {
  const t = useT();
  if (reward.kind === "player" && reward.player) {
    const mine = squad.players.some((p) => p.id === reward.player.id);
    return <span className={`fx-status${mine ? " ok" : ""}`}>{mine ? t("inTeam") : t("notInTeam")}</span>;
  }
  if (reward.kind === "points" && bestWeek != null) {
    return <span className={`fx-status${bestWeek >= reward.threshold ? " ok" : ""}`}>{t("bestWeek", { n: Math.round(bestWeek) })}</span>;
  }
  if (reward.kind === "tier" && standing) {
    const ok = TIER_ORDER.indexOf(standing.tier) >= TIER_ORDER.indexOf(reward.tier);
    return <span className={`fx-status${ok ? " ok" : ""}`}>{t("youAre", { tier: t(standing.tier) })}</span>;
  }
  return null;
}

function PrizeCard({ reward, squad, bestWeek, standing }) {
  const t = useT();
  return (
    <li className="fx-prize">
      <img src={reward.sponsor.logo_url} alt={reward.sponsor.name} />
      <div>
        <b>{reward.title}</b>
        <span>{reward.description}</span>
        <Status reward={reward} squad={squad} bestWeek={bestWeek} standing={standing} />
      </div>
      {reward.kind === "rank" ? <em className={`fx-place${reward.rank_from === 1 ? " gold" : ""}`}>{placeText(reward, t)}</em>
        : reward.kind === "player" && reward.player ? <PlayerToken player={reward.player} sub={t("pts", { n: `${reward.threshold}+` })} />
          : reward.kind === "points" ? <em>{t("pts", { n: reward.threshold })}</em>
            : <em className={`fx-place ${reward.tier}`}><TierIcon tier={reward.tier} /> {t(reward.tier)}</em>}
    </li>
  );
}

function wonFor(v, t) {
  if (v.reward.kind === "rank") return t("wonRank", { rank: v.rank });
  if (v.reward.kind === "player") return t("wonPlayer");
  if (v.reward.kind === "points") return t("wonPoints", { n: v.reward.threshold });
  return t("wonTier");
}

function Vouchers() {
  const t = useT();
  const [list, setList] = useState(null);
  const [page, setPage] = useState(0);
  const [shown, setShown] = useState({});
  useEffect(() => { getVouchers().then(setList, () => setList([])); }, []);
  if (!list) return <Spinner />;
  if (!list.length) return null;
  const slice = list.slice(page * VOUCHER_PAGE, (page + 1) * VOUCHER_PAGE);
  return (
    <section className="fx-section">
      <div className="fx-section-head"><h3>{t("vouchers")}</h3><span>{t("won", { n: list.length })}</span></div>
      <ul className="fx-vouchers">
        {slice.map((v) => (
          <li key={v.id}>
            <img src={v.reward.sponsor.logo_url} alt={v.reward.sponsor.name} />
            <div>
              <b>{v.reward.title}</b>
              <span>{t("voucherLine", { gw: v.gameweek, how: wonFor(v, t), date: new Date(v.expires_at).toLocaleDateString("fi-FI") })}</span>
            </div>
            {shown[v.id] ? <code>{v.code}</code>
              : <button type="button" onClick={() => setShown({ ...shown, [v.id]: true })}><Ticket size={14} /> {t("showCode")}</button>}
          </li>
        ))}
      </ul>
      <Pager page={page} pages={Math.ceil(list.length / VOUCHER_PAGE)} onPage={setPage} />
    </section>
  );
}

/** Prizes set by each brand: top 3 places, a named player scoring, a points target, or a season tier. */
export default function Prizes({ rewards, squad, nextGw }) {
  const t = useT();
  const now = useNow();
  const [bestWeek, setBestWeek] = useState(null);
  useEffect(() => { getSquadHistory().then((h) => setBestWeek(Math.max(0, ...h.map((x) => Number(x.total))))).catch(() => {}); }, [squad.id]);
  const standing = squad.standing;
  const weekly = rewards.filter((r) => r.period === "week");
  const season = rewards.filter((r) => r.period === "season");
  const locks = nextGw && countdown(nextGw.deadline, now, t.lang);
  const card = (r) => <PrizeCard key={r.id} reward={r} squad={squad} bestWeek={bestWeek} standing={standing} />;

  return (
    <>
      {standing && (
        <section className={`fx-section fx-standing ${standing.tier}`}>
          <TierBadge tier={standing.tier} size="lg" />
          <p>{t("standing", { rank: standing.rank, managers: standing.managers })}
            {standing.next_tier && standing.places_to_next > 0 && <> {standing.places_to_next > 1
              ? t("placesTo", { n: standing.places_to_next, tier: t(standing.next_tier) }) : t("placeTo", { tier: t(standing.next_tier) })}</>}
          </p>
        </section>
      )}
      {weekly.length > 0 && (
        <section className="fx-section">
          <div className="fx-section-head"><h3>{t("gwPrizes", { n: nextGw?.number })}</h3>{locks && <span>{t("starts", { left: locks })}</span>}</div>
          <ul className="fx-prizes">{weekly.map(card)}</ul>
        </section>
      )}
      {season.length > 0 && (
        <section className="fx-section">
          <div className="fx-section-head"><h3>{t("seasonPrizes")}</h3></div>
          <ul className="fx-prizes">{season.map(card)}</ul>
        </section>
      )}
      <Vouchers />
    </>
  );
}
