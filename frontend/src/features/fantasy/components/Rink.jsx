import { photoOf } from "../lib/fantasyPreload";
import { useT } from "../lib/lamariText";

/** Fantasy lineup drawn on an ice rink: two forward lines, two defence pairs, the goalie in the crease,
 *  and the bench below. Tapping a starter calls onPick(player). */

export function PlayerToken({ player, badge, sub, onClick, dim }) {
  const initials = `${player.first_name?.[0] || ""}${player.last_name?.[0] || ""}`;
  return (
    <button type="button" className={`fx-token${dim ? " dim" : ""}`} onClick={onClick} aria-label={`${player.first_name} ${player.last_name}`}>
      <span className="fx-face">
        {photoOf(player) && <img src={photoOf(player)} alt="" referrerPolicy="no-referrer" onLoad={(e) => e.currentTarget.classList.add("ready")}
          onError={(e) => { e.currentTarget.style.display = "none"; }} />}
        <span className="fx-initials">{initials}</span>
        {badge && <span className={`fx-badge${badge === "VC" ? " vc" : ""}`}>{badge}</span>}
        {(player.injured || player.suspended) && <span className="fx-flag">{player.injured ? "INJ" : "SUS"}</span>}
      </span>
      <span className="fx-name">{player.last_name}</span>
      <span className="fx-sub">{sub}</span>
    </button>
  );
}

export default function Rink({ lineup, byId, pointsFor, onPick }) {
  const t = useT();
  const starters = (lineup?.starters || []).map((id) => byId[id]).filter(Boolean);
  const bench = (lineup?.bench || []).map((id) => byId[id]).filter(Boolean);
  const of = (pos) => starters.filter((p) => p.position === pos);
  const forwards = of("F");
  const badge = (p) => (p.id === lineup.captain ? "C" : p.id === lineup.vice_captain ? "VC" : null);
  const token = (p) => <PlayerToken key={p.id} player={p} badge={badge(p)} sub={pointsFor(p)} onClick={() => onPick(p)} />;

  return (
    <>
      <div className="fx-rink">
        <div className="fx-rink-lines" aria-hidden="true"><i className="blue" /><i className="red" /><i className="blue" /><b className="crease" /></div>
        <div className="fx-row-label">{t("forwards")}</div>
        <div className="fx-row">{forwards.slice(0, 3).map(token)}</div>
        <div className="fx-row">{forwards.slice(3).map(token)}</div>
        <div className="fx-row-label">{t("defence")}</div>
        <div className="fx-row">{of("D").map(token)}</div>
        <div className="fx-row-label">{t("goalie")}</div>
        <div className="fx-row">{of("G").map(token)}</div>
      </div>
      <div className="fx-bench">
        <span>{t("bench")}</span>
        <div className="fx-row">{bench.map((p) => <PlayerToken key={p.id} player={p} sub={pointsFor(p)} dim onClick={() => onPick(p, true)} />)}</div>
      </div>
    </>
  );
}
