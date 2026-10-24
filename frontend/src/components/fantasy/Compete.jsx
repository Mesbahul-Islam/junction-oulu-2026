import { Copy, UserPlus } from "lucide-react";
import { useEffect, useState } from "react";

import { createLeague, getLeaderboard, inviteToLeague, joinLeague, searchManagers } from "../../lib/api";
import { Spinner } from "../Spinner";
import { MEDAL, Pager, prizeFor, TierBadge } from "./util";
import { useT } from "../../lib/lamariText";
import { forget } from "../../lib/fantasyPreload";

const PAGE = 20;
const tierOf = (rank, total) => (rank === 1 ? "diamond" : rank / total <= 0.1 ? "gold" : rank / total <= 0.35 ? "silver" : null);

function Board({ season, leagues, me, rewards }) {
  const t = useT();
  const lastPlayed = [...season.gameweeks].reverse().find((g) => g.status !== "upcoming")?.number;
  const [period, setPeriod] = useState("season");
  const [scope, setScope] = useState("global");
  const [page, setPage] = useState(0);
  const [data, setData] = useState(null);

  useEffect(() => { setPage(0); }, [period, scope]);
  useEffect(() => {
    const q = { period, limit: PAGE, offset: page * PAGE };
    if (period === "week") q.gameweek = lastPlayed;
    if (period === "day") q.date = new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Helsinki" });
    if (scope === "oulu") Object.assign(q, { scope: "community", community: "oulu" });
    else if (scope !== "global") Object.assign(q, { scope: "league", league: scope });
    setData(null);
    getLeaderboard(q).then(setData, () => setData({ rows: [], total: 0 }));
  }, [period, scope, page, lastPlayed]);

  const prizePeriod = period === "week" ? "week" : period === "season" ? "season" : null;
  const pages = data ? Math.ceil(data.total / PAGE) : 0;
  const myPage = data?.me ? Math.floor((data.me.rank - 1) / PAGE) : null;

  return (
    <>
      <div className="fx-seg">
        {[["season", t("seasonTab")], ["week", t("gwTab", { n: lastPlayed ?? "" })], ["day", t("today")]].map(([v, l]) => (
          <button key={v} type="button" className={period === v ? "on" : ""} onClick={() => setPeriod(v)}>{l}</button>
        ))}
      </div>
      <div className="fx-chips">
        <button type="button" className={scope === "global" ? "on" : ""} onClick={() => setScope("global")}>{t("finland")}</button>
        <button type="button" className={scope === "oulu" ? "on" : ""} onClick={() => setScope("oulu")}>{t("oulu")}</button>
        {leagues.map((l) => <button key={l.id} type="button" className={scope === String(l.id) ? "on" : ""} onClick={() => setScope(String(l.id))}>{l.name}</button>)}
      </div>
      {!data ? <Spinner /> : !data.rows.length ? <p className="fx-empty">{t("noPoints")}</p> : (
        <>
          <ol className="fx-board">
            {data.rows.map((r) => {
              // Prizes exist for the Finland and Oulu boards (season and gameweek), not for private leagues.
              const prize = prizePeriod && (scope === "global" || scope === "oulu") ? prizeFor(r.rank, rewards, prizePeriod, scope) : null;
              return (
                <li key={r.squad_id} className={r.manager === me.username ? "me" : ""}>
                  <span className={`fx-rank${MEDAL[r.rank] ? " medal" : ""}`}>{MEDAL[r.rank] || r.rank}</span>
                  <span className="fx-who">
                    <b>{r.squad_name}</b>
                    <small>@{r.manager} {period === "season" && scope === "global" && tierOf(r.rank, data.total) && <TierBadge tier={tierOf(r.rank, data.total)} />}</small>
                  </span>
                  {prize && <img className="fx-row-prize" src={prize.sponsor.logo_url} alt={`${prize.sponsor.name}: ${prize.title}`} title={`${prize.sponsor.name}: ${prize.title}`} />}
                  <span className="fx-pts">{Math.round(r.points)}</span>
                </li>
              );
            })}
          </ol>
          <Pager page={page} pages={pages} onPage={setPage} />
          {myPage !== null && myPage !== page && <button type="button" className="fx-link center" onClick={() => setPage(myPage)}>{t("jumpToMe", { n: data.me.rank })}</button>}
        </>
      )}
    </>
  );
}

function InviteBox({ league, onDone }) {
  const t = useT();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState([]);
  const [msg, setMsg] = useState("");
  useEffect(() => {
    const handle = q.replace(/^@/, "");
    if (handle.length < 2) { setHits([]); return undefined; }
    const t = setTimeout(() => searchManagers(handle).then(setHits).catch(() => setHits([])), 250);
    return () => clearTimeout(t);
  }, [q]);
  const invite = async (username) => {
    try { onDone(await inviteToLeague(league.id, username)); setMsg(t("joined", { user: username, league: league.name })); setQ(""); }
    catch (e) { setMsg(e.message); }
  };
  const taken = new Set(league.members.map((m) => m.username));
  return (
    <div className="fx-invite">
      <label className="fx-input"><UserPlus size={16} />
        <input placeholder={t("inviteFriend")} value={q} onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && q.trim() && invite(q.trim().replace(/^@/, ""))} />
      </label>
      {hits.filter((h) => !taken.has(h.username)).map((h) => (
        <button key={h.username} type="button" className="fx-hit" onClick={() => invite(h.username)}>@{h.username} <small>{h.squad_name}</small><span>{t("invite")}</span></button>
      ))}
      {msg && <p className="fx-note">{msg}</p>}
    </div>
  );
}

function Leagues({ leagues, setLeagues, me }) {
  const t = useT();
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [open, setOpen] = useState(null);

  const replace = (league) => { forget("leagues"); setLeagues((list) => [league, ...list.filter((l) => l.id !== league.id)]); };
  const run = async (fn) => { setError(""); try { const l = await fn(); replace(l); setOpen(l.id); setName(""); setCode(""); } catch (e) { setError(e.message); } };

  return (
    <>
      <div className="fx-league-form">
        <div className="fx-row-form">
          <input placeholder={t("newLeague")} value={name} maxLength={60} onChange={(e) => setName(e.target.value)} />
          <button type="button" disabled={!name.trim()} onClick={() => run(() => createLeague(name.trim()))}>{t("create")}</button>
        </div>
        <div className="fx-row-form">
          <input placeholder={t("inviteCode")} value={code} maxLength={12} onChange={(e) => setCode(e.target.value.toUpperCase())} />
          <button type="button" disabled={code.trim().length < 4} onClick={() => run(() => joinLeague(code.trim()))}>{t("join")}</button>
        </div>
        {error && <div className="error">{error}</div>}
      </div>
      
      {leagues.map((l) => {
        const myRank = l.members.findIndex((m) => m.username === me.username) + 1;
        return (
          <div key={l.id} className="fx-league">
            <button type="button" className="fx-league-head" onClick={() => setOpen(open === l.id ? null : l.id)}>
              <span><b>{l.name}</b><small>{t("managers", { n: l.member_count })}{myRank ? t("youRank", { n: myRank }) : ""}</small></span>
              <span className="fx-code" onClick={(e) => { e.stopPropagation(); navigator.clipboard?.writeText(l.code); }} title={t("copyCode")}>{l.code} <Copy size={12} /></span>
            </button>
            {open === l.id && (
              <>
                <ol className="fx-board">
                  {l.members.map((m, i) => (
                    <li key={m.squad_id} className={m.username === me.username ? "me" : ""}>
                      <span className={`fx-rank${MEDAL[i + 1] ? " medal" : ""}`}>{MEDAL[i + 1] || i + 1}</span>
                      <span className="fx-who"><b>@{m.username}</b><small>{m.squad_name}</small></span>
                      <span className="fx-pts">{Math.round(m.total_points)}</span>
                    </li>
                  ))}
                </ol>
                <InviteBox league={l} onDone={replace} />
              </>
            )}
          </div>
        );
      })}
    </>
  );
}

export default function Compete({ season, leagues, setLeagues, me, rewards }) {
  const t = useT();
  const [view, setView] = useState("board");
  return (
    <section className="fx-section">
      <div className="fx-seg small">
        <button type="button" className={view === "board" ? "on" : ""} onClick={() => setView("board")}>{t("leaderboards")}</button>
        <button type="button" className={view === "leagues" ? "on" : ""} onClick={() => setView("leagues")}>{t("privateLeagues")}</button>
      </div>
      {view === "board" ? <Board season={season} leagues={leagues} me={me} rewards={rewards} />
        : <Leagues leagues={leagues} setLeagues={setLeagues} me={me} />}
    </section>
  );
}
