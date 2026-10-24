import { Check, Plus, Search, Wand2 } from "lucide-react";
import { useMemo, useState } from "react";

import { createSquad } from "../../lib/api";
import { photoOf } from "../../lib/fantasyPreload";
import { useT } from "../../lib/lamariText";

// Mirrors backend/apps/fantasy/rules.py (the server validates again on save).
export const SQUAD = { G: 2, D: 5, F: 8 };
const SQUAD_SIZE = 15;
const MAX_PER_TEAM = 3;
const MIN_PRICE = 4;
const LIST_PAGE = 25;

/** "Make your team": pick 15 players under the budget, max 3 from one Liiga team. */
export default function SquadBuilder({ season, players, onCreated }) {
  const t = useT();
  const POS_NAME = { G: t("goalies"), D: t("defenders"), F: t("forwardsTab") };
  const budget = Number(season.budget);
  const [picked, setPicked] = useState([]);
  const [pos, setPos] = useState("G");
  const [search, setSearch] = useState("");
  const [shown, setShown] = useState(LIST_PAGE);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const byId = useMemo(() => Object.fromEntries(players.map((p) => [p.id, p])), [players]);
  const chosen = picked.map((id) => byId[id]);
  const spent = chosen.reduce((s, p) => s + Number(p.price), 0);
  const count = (position) => chosen.filter((p) => p.position === position).length;
  const fromTeam = (teamId) => chosen.filter((p) => p.team_id === teamId).length;

  /** Why a player can't be added right now ("" if they can). */
  const blocked = (p, list = chosen, money = spent) => {
    if (list.filter((x) => x.position === p.position).length >= SQUAD[p.position]) return t("full_", { pos: POS_NAME[p.position] });
    if (list.filter((x) => x.team_id === p.team_id).length >= MAX_PER_TEAM) return t("threeFrom", { team: p.team });
    const slotsLeft = SQUAD_SIZE - list.length - 1;
    if (money + Number(p.price) + slotsLeft * MIN_PRICE > budget) return t("overBudget");
    return "";
  };
  const toggle = (p) => setPicked((ids) => (ids.includes(p.id) ? ids.filter((i) => i !== p.id) : blocked(p) ? ids : [...ids, p.id]));

  // Quick pick: fill the open slots with the best points-per-price players that still fit.
  const quickPick = () => {
    const list = [...chosen];
    let money = spent;
    const pool = players.filter((p) => !picked.includes(p.id) && !p.injured && !p.suspended)
      .sort((a, b) => b.total_points / b.price - a.total_points / a.price);
    for (const p of pool) {
      if (list.length === SQUAD_SIZE) break;
      if (!blocked(p, list, money)) { list.push(p); money += Number(p.price); }
    }
    setPicked(list.map((p) => p.id));
  };

  const matching = players
    .filter((p) => p.position === pos)
    .filter((p) => !search || `${p.first_name} ${p.last_name} ${p.team}`.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => b.total_points - a.total_points);
  const visible = matching.slice(0, shown);

  const save = async () => {
    setSaving(true); setError("");
    try { onCreated(await createSquad(name.trim() || "My team", picked)); }
    catch (e) { setError(e.message); setSaving(false); }
  };

  const left = budget - spent;
  return (
    <section>
      <div className="fx-hero">
        <h2>{t("makeTeam")}</h2>
        <p>{t("makeTeamHelp")}</p>
        <div className="fx-budget">
          <div><b>{left.toFixed(1)}</b><span>{t("budgetLeft")}</span></div>
          <div><b>{picked.length}/15</b><span>{t("players")}</span></div>
          <button type="button" className="fx-quick" onClick={quickPick} disabled={picked.length === SQUAD_SIZE}><Wand2 size={16} /> {t("quickPick")}</button>
        </div>
        <div className="fx-meter"><span style={{ width: `${Math.min(100, (spent / budget) * 100)}%` }} /></div>
      </div>

      <div className="fx-tabs">
        {Object.keys(SQUAD).map((p) => (
          <button key={p} type="button" className={pos === p ? "on" : ""} onClick={() => { setPos(p); setShown(LIST_PAGE); }}>
            {POS_NAME[p]} <small>{count(p)}/{SQUAD[p]}</small>
          </button>
        ))}
      </div>
      <label className="fx-search"><Search size={16} /><input placeholder={t("search")} value={search} onChange={(e) => { setSearch(e.target.value); setShown(LIST_PAGE); }} /></label>

      <div className="fx-list">
        {visible.map((p) => {
          const isIn = picked.includes(p.id);
          const why = isIn ? "" : blocked(p);
          return (
            <button key={p.id} type="button" className={`fx-prow${isIn ? " in" : ""}${why ? " off" : ""}`} onClick={() => toggle(p)}>
              <span className="fx-face sm">{photoOf(p) && <img src={photoOf(p)} alt="" loading="lazy" referrerPolicy="no-referrer" onLoad={(e) => e.currentTarget.classList.add("ready")} onError={(e) => { e.currentTarget.style.display = "none"; }} />}<span className="fx-initials">{p.first_name[0]}{p.last_name[0]}</span></span>
              <span className="fx-pinfo"><b>{p.first_name} {p.last_name}</b><small>{p.team}{p.injured ? `, ${t("injured")}` : ""}{why ? `. ${why}` : ""}</small></span>
              <span className="fx-pnum"><b>{Math.round(p.total_points)}</b><small>{t("ptsShort")}</small></span>
              <span className="fx-pnum"><b>{p.price}</b><small>{t("price")}</small></span>
              <span className="fx-add">{isIn ? <Check size={18} /> : <Plus size={18} />}</span>
            </button>
          );
        })}
      </div>
      {shown < matching.length && (
        <button type="button" className="fx-more" onClick={() => setShown(shown + LIST_PAGE)}>
          {t("showMore", { n: matching.length - shown })}
        </button>
      )}

      {picked.length === SQUAD_SIZE && (
        <div className="fx-save">
          {error && <div className="error">{error}</div>}
          <input placeholder={t("teamName")} maxLength={60} value={name} onChange={(e) => setName(e.target.value)} />
          <button type="button" className="btn-primary" style={{ marginTop: 10 }} onClick={save} disabled={saving}>{saving ? t("saving") : t("createTeam")}</button>
        </div>
      )}
    </section>
  );
}
