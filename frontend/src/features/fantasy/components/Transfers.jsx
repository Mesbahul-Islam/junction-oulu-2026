import { ArrowLeft, Minus, Plus, Shuffle, X } from "lucide-react";
import { useMemo, useState } from "react";

import { makeTransfers, shakeUp } from "@/features/fantasy/api";
import { forget, photoOf } from "../lib/fantasyPreload";
import { useT } from "../lib/lamariText";
import { isPremium, MAX_PREMIUM } from "./SquadBuilder";

const MAX_PER_TEAM = 3;

function Face({ p }) {
  return (
    <span className="fx-face sm">
      {photoOf(p) && <img src={photoOf(p)} alt="" referrerPolicy="no-referrer" onLoad={(e) => e.currentTarget.classList.add("ready")} onError={(e) => { e.currentTarget.style.display = "none"; }} />}
      <span className="fx-initials">{p.first_name[0]}{p.last_name[0]}</span>
    </span>
  );
}

/** Change your team. Every new player costs points by his ranking, and you need enough points.
 *  Shake up suggests swaps; nothing changes until you tap Save changes. */
export default function Transfers({ squad, players, teams, onDone, onClose }) {
  const t = useT();
  const available = Math.floor(squad.points_available ?? 0);
  const [out, setOut] = useState(null);
  const [team, setTeam] = useState(null);
  const [inn, setInn] = useState(null);
  const [limit, setLimit] = useState(Math.min(8, Math.max(1, available)));
  const [plan, setPlan] = useState(null); // suggested swaps from Shake up, not saved yet
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(null);
  const [error, setError] = useState("");

  const owned = useMemo(() => new Set(squad.players.map((p) => p.id)), [squad]);
  const perTeam = useMemo(() => squad.players.reduce((m, p) => ({ ...m, [p.team_id]: (m[p.team_id] || 0) + 1 }), {}), [squad]);
  const cost = (p) => p.transfer_cost ?? 0;
  const money = out ? Number(squad.bank) + Number(out.purchase_price ?? out.price) : 0;

  const premiumNow = squad.players.filter(isPremium).length;
  const fits = (p) => !owned.has(p.id) && p.position === out.position && Number(p.price) <= money
    && (perTeam[p.team_id] || 0) - (p.team_id === out.team_id ? 1 : 0) < MAX_PER_TEAM
    && (!isPremium(p) || isPremium(out) || premiumNow < MAX_PREMIUM);
  const options = out ? players.filter((p) => fits(p) && (!team || p.team_id === team)).sort((a, b) => b.total_points - a.total_points) : [];

  const reset = () => { setOut(null); setInn(null); setTeam(null); setPlan(null); };
  const suggest = async () => {
    setBusy(true); setError(""); setSaved(null);
    try { setPlan(await shakeUp(limit)); } catch (e) { setError(e.message); }
    setBusy(false);
  };
  const save = async (outIds, inIds) => {
    setBusy(true); setError("");
    try {
      const res = await makeTransfers(outIds, inIds);
      forget("squad"); setSaved(res.transfers); onDone(res.squad); reset();
    } catch (e) { setError(e.message); }
    setBusy(false);
  };

  return (
    <div className="fx-sheet-wrap" onClick={onClose}>
      <div className="fx-sheet tall" onClick={(e) => e.stopPropagation()}>
        <div className="fx-sheet-head">
          {out || plan ? <button type="button" onClick={reset} aria-label={t("back")}><ArrowLeft size={20} /></button> : <span />}
          <b>{out ? t("replacePlayer", { name: out.last_name }) : t("changeTeam")}</b>
          <button type="button" onClick={onClose} aria-label={t("close")}><X size={20} /></button>
        </div>
        <p className="fx-note"><b>{t("pointsToSpend", { n: available })}</b> {t("costRule")}</p>
        {error && <div className="fx-error">{error}</div>}

        {saved && !out && !plan && (
          <ul className="fx-swaps">
            {saved.map((r) => <li key={r.id}>{r.player_out_name} <b>→</b> {r.player_in_name}<em>-{r.point_cost} {t("ptsShort")}</em></li>)}
          </ul>
        )}

        {plan && (
          <div className="fx-plan">
            <h4 className="fx-sheet-team">{t("suggested")}</h4>
            <ul className="fx-pick-list">
              {plan.swaps.map((s) => (
                <li key={s.in.id}><div className="fx-plan-row">
                  <Face p={s.out} /><span className="fx-pinfo"><b>{s.out.last_name}</b><small>{s.out.team}</small></span>
                  <b className="fx-arrow">→</b>
                  <Face p={s.in} /><span className="fx-pinfo"><b>{s.in.last_name}</b><small>{s.in.team}</small></span>
                  <em className="fx-cost">-{s.cost}</em>
                </div></li>
              ))}
            </ul>
            <div className="fx-confirm">
              <span>{t("planTotal", { n: plan.total_cost, left: available - plan.total_cost })}</span>
              <button type="button" className="fx-ghost" disabled={busy} onClick={suggest}>{t("tryAgain")}</button>
              <button type="button" className="fx-go" disabled={busy || plan.total_cost > available}
                onClick={() => save(plan.swaps.map((s) => s.out.id), plan.swaps.map((s) => s.in.id))}>{t("saveChanges")}</button>
            </div>
          </div>
        )}

        {!out && !plan && (
          <>
            <div className="fx-shake">
              <div>
                <b>{t("shakeUp")}</b>
                <span>{t("shakeUpHelp")}</span>
              </div>
              <div className="fx-stepper">
                <button type="button" onClick={() => setLimit(Math.max(1, limit - 1))} aria-label="-"><Minus size={16} /></button>
                <span>{limit} {t("ptsShort")}</span>
                <button type="button" onClick={() => setLimit(Math.min(available, limit + 1))} aria-label="+"><Plus size={16} /></button>
              </div>
              <button type="button" className="fx-go" disabled={busy || available < 1} onClick={suggest}><Shuffle size={16} /> {t("shakeUpGo")}</button>
            </div>
            <h4 className="fx-sheet-team">{t("pickToReplace")}</h4>
            <ul className="fx-pick-list">
              {squad.players.map((p) => (
                <li key={p.id}><button type="button" onClick={() => { setOut(p); setSaved(null); }}>
                  <Face p={p} /><span className="fx-pinfo"><b>{p.first_name} {p.last_name}</b><small>{p.team}, {p.position}</small></span>
                  <span className="fx-pnum"><b>{Math.round(p.total_points)}</b><small>{t("ptsShort")}</small></span>
                </button></li>
              ))}
            </ul>
          </>
        )}

        {out && (
          <>
            <div className="fx-chips">
              <button type="button" className={!team ? "on" : ""} onClick={() => setTeam(null)}>{t("allTeams")}</button>
              {teams.map((tm) => <button key={tm.id} type="button" className={team === tm.id ? "on" : ""} onClick={() => setTeam(tm.id)}>{tm.name}</button>)}
            </div>
            <ul className="fx-pick-list">
              {options.slice(0, 40).map((p) => {
                const tooDear = cost(p) > available;
                return (
                  <li key={p.id} className={`${inn?.id === p.id ? "on" : ""}${tooDear ? " off" : ""}`}><button type="button" disabled={tooDear} onClick={() => setInn(p)}>
                    <Face p={p} /><span className="fx-pinfo"><b>{p.first_name} {p.last_name}</b><small>{p.team}, {p.price}</small></span>
                    <span className="fx-pnum"><b>{Math.round(p.total_points)}</b><small>{t("ptsShort")}</small></span>
                    <em className="fx-cost">-{cost(p)}</em>
                  </button></li>
                );
              })}
              {!options.length && <li className="fx-note">{t("noOptions")}</li>}
            </ul>
            {inn && (
              <div className="fx-confirm">
                <span>{t("swapLine", { a: out.last_name, b: inn.last_name })} {t("costsPoints", { n: cost(inn) })}</span>
                <button type="button" className="fx-go" disabled={busy} onClick={() => save([out.id], [inn.id])}>{t("saveChanges")}</button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
