import { ArrowLeft, Minus, Plus, Shuffle, X } from "lucide-react";
import { useMemo, useState } from "react";

import { makeTransfers, shakeUp } from "@/features/fantasy/api";
import { forget, photoOf } from "../lib/fantasyPreload";
import { useT } from "../lib/lamariText";

const MAX_PER_TEAM = 3;

function Face({ p }) {
  return (
    <span className="fx-face sm">
      {photoOf(p) && <img src={photoOf(p)} alt="" referrerPolicy="no-referrer" onLoad={(e) => e.currentTarget.classList.add("ready")} onError={(e) => { e.currentTarget.style.display = "none"; }} />}
      <span className="fx-initials">{p.first_name[0]}{p.last_name[0]}</span>
    </span>
  );
}

/** Change your team: shake it up within a points limit, or swap one player by picking a team and a player. */
export default function Transfers({ squad, players, teams, onDone, onClose }) {
  const t = useT();
  const [out, setOut] = useState(null);
  const [team, setTeam] = useState(null);
  const [inn, setInn] = useState(null);
  const [limit, setLimit] = useState(8);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const owned = useMemo(() => new Set(squad.players.map((p) => p.id)), [squad]);
  const perTeam = useMemo(() => squad.players.reduce((m, p) => ({ ...m, [p.team_id]: (m[p.team_id] || 0) + 1 }), {}), [squad]);
  const cost = (p) => (squad.free_changes ? 0 : p.transfer_cost ?? 0);
  const money = out ? Number(squad.bank) + Number(out.purchase_price ?? out.price) : 0;

  const fits = (p) => !owned.has(p.id) && p.position === out.position && Number(p.price) <= money
    && (perTeam[p.team_id] || 0) - (p.team_id === out.team_id ? 1 : 0) < MAX_PER_TEAM;
  const options = out ? players.filter((p) => fits(p) && (!team || p.team_id === team)).sort((a, b) => b.total_points - a.total_points) : [];

  const finish = (res) => { forget("squad"); setResult(res.transfers); onDone(res.squad); setOut(null); setInn(null); setTeam(null); };
  const run = async (fn) => {
    setBusy(true); setError("");
    try { finish(await fn()); } catch (e) { setError(e.message); }
    setBusy(false);
  };

  return (
    <div className="fx-sheet-wrap" onClick={onClose}>
      <div className="fx-sheet tall" onClick={(e) => e.stopPropagation()}>
        <div className="fx-sheet-head">
          {out ? <button type="button" onClick={() => { setOut(null); setInn(null); setTeam(null); }} aria-label={t("back")}><ArrowLeft size={20} /></button> : <span />}
          <b>{out ? t("replacePlayer", { name: out.last_name }) : t("changeTeam")}</b>
          <button type="button" onClick={onClose} aria-label={t("close")}><X size={20} /></button>
        </div>
        <p className="fx-note">{squad.free_changes ? t("freeChanges") : t("costRule")}{!squad.free_changes && squad.points_spent > 0 && ` ${t("spentSoFar", { n: squad.points_spent })}`}</p>
        {error && <div className="fx-error">{error}</div>}

        {result && !out && (
          <ul className="fx-swaps">
            {result.map((r) => <li key={r.id}>{r.player_out_name} <b>→</b> {r.player_in_name}{r.point_cost > 0 && <em>-{r.point_cost} {t("ptsShort")}</em>}</li>)}
          </ul>
        )}

        {!out && (
          <>
            <div className="fx-shake">
              <div>
                <b>{t("shakeUp")}</b>
                <span>{t("shakeUpHelp")}</span>
              </div>
              {!squad.free_changes && (
                <div className="fx-stepper">
                  <button type="button" onClick={() => setLimit(Math.max(1, limit - 1))} aria-label="-"><Minus size={16} /></button>
                  <span>{limit} {t("ptsShort")}</span>
                  <button type="button" onClick={() => setLimit(Math.min(40, limit + 1))} aria-label="+"><Plus size={16} /></button>
                </div>
              )}
              <button type="button" className="fx-go" disabled={busy} onClick={() => run(() => shakeUp(squad.free_changes ? 40 : limit))}><Shuffle size={16} /> {t("shakeUpGo")}</button>
            </div>
            <h4 className="fx-sheet-team">{t("pickToReplace")}</h4>
            <ul className="fx-pick-list">
              {squad.players.map((p) => (
                <li key={p.id}><button type="button" onClick={() => { setOut(p); setResult(null); }}>
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
              {options.slice(0, 40).map((p) => (
                <li key={p.id} className={inn?.id === p.id ? "on" : ""}><button type="button" onClick={() => setInn(p)}>
                  <Face p={p} /><span className="fx-pinfo"><b>{p.first_name} {p.last_name}</b><small>{p.team}, {p.price}</small></span>
                  <span className="fx-pnum"><b>{Math.round(p.total_points)}</b><small>{t("ptsShort")}</small></span>
                  <em className="fx-cost">{cost(p) ? `-${cost(p)}` : t("free")}</em>
                </button></li>
              ))}
              {!options.length && <li className="fx-note">{t("noOptions")}</li>}
            </ul>
            {inn && (
              <div className="fx-confirm">
                <span>{t("swapLine", { a: out.last_name, b: inn.last_name })}{cost(inn) ? ` ${t("costsPoints", { n: cost(inn) })}` : ""}</span>
                <button type="button" className="fx-go" disabled={busy} onClick={() => run(() => makeTransfers([out.id], [inn.id]))}>{t("confirm")}</button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
