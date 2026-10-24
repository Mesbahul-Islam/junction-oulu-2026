import { ChevronLeft, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import Chat from "../components/fantasy/Chat";
import Coach from "../components/fantasy/Coach";
import Compete from "../components/fantasy/Compete";
import Matches from "../components/fantasy/Matches";
import Prizes from "../components/fantasy/Prizes";
import Rink, { PlayerToken } from "../components/fantasy/Rink";
import Splash from "../components/fantasy/Splash";
import SquadBuilder from "../components/fantasy/SquadBuilder";
import { countdown, finnishTime, TierBadge, useNow } from "../components/fantasy/util";
import { Spinner } from "../components/Spinner";
import { getFixtures, getLineup, getSquadHistory, setLineup } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useT } from "../lib/lamariText";
import { cached, forget, loadFantasy, photoOf, warmPhotos } from "../lib/fantasyPreload";

const SPLASH_MS = 3000;
const SPLASH_KEY = "lamari-splash-seen";

// ------------------------------------------------------------------ upcoming games

function MatchCarousel({ fixtures, now, onOpen }) {
  const t = useT();
  if (!fixtures.length) return null;
  return (
    <div className="fx-matches" role="list">
      {fixtures.map((f) => {
        const left = countdown(f.starts_at, now, t.lang);
        const soon = new Date(f.starts_at) - now < 864e5; // under a day: show the countdown
        return (
          <button key={f.id} type="button" role="listitem" className={`fx-match${f.status === "live" ? " live" : ""}${soon && f.status !== "live" ? " soon" : ""}`} onClick={() => onOpen(f)}>
            <span className="fx-vs">
              {f.home.logo_url && <img src={f.home.logo_url} alt="" />}<b>{f.home.abbreviation || f.home.name}</b>
              <i>vs</i>
              <b>{f.away.abbreviation || f.away.name}</b>{f.away.logo_url && <img src={f.away.logo_url} alt="" />}
            </span>
            <em className={f.status === "live" || (left && soon) ? "hot" : ""}>
              {f.status === "live" ? t("live") : f.status === "finished" ? `${f.home_goals}-${f.away_goals}` : left && soon ? t("startsIn", { left }) : finnishTime(f.starts_at, t.locale)}
            </em>
          </button>
        );
      })}
    </div>
  );
}

function MatchSheet({ fixture, players, mine, onClose }) {
  const t = useT();
  const top = (team) => players.filter((p) => p.team_id === team.id).sort((a, b) => b.total_points - a.total_points).slice(0, 4);
  return (
    <div className="fx-sheet-wrap" onClick={onClose}>
      <div className="fx-sheet" onClick={(e) => e.stopPropagation()}>
        <div className="fx-sheet-head"><b>{fixture.home.name} vs {fixture.away.name}</b><button type="button" onClick={onClose} aria-label={t("close")}><X size={20} /></button></div>
        <p className="fx-note">{t("topScorers", { time: finnishTime(fixture.starts_at, t.locale) })}</p>
        {[fixture.home, fixture.away].map((team) => (
          <div key={team.id}>
            <h4 className="fx-sheet-team">{team.name}</h4>
            <div className="fx-row start">
              {top(team).map((p) => <PlayerToken key={p.id} player={p} badge={mine.has(p.id) ? "✓" : null} sub={t("pts", { n: Math.round(p.total_points) })} />)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ my team

function MyTeam({ squad, byId, sponsor }) {
  const t = useT();
  const [lineup, setLineupState] = useState(null);
  const [history, setHistory] = useState([]);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    getLineup().then(setLineupState);
    getSquadHistory().then(setHistory);
  }, [squad.id]);

  const last = [...history].reverse().find((h) => h.detail?.length);
  const lastPts = Object.fromEntries((last?.detail || []).map((d) => [d.player, d.points * d.multiplier]));
  const pointsFor = (p) => (p.id in lastPts ? t("pts", { n: lastPts[p.id] }) : `${p.price}`);

  const makeCaptain = async (p, onBench) => {
    if (onBench || p.id === lineup.captain) return;
    const vice = p.id === lineup.vice_captain ? lineup.captain : lineup.vice_captain;
    try {
      setLineupState(await setLineup({ starters: lineup.starters, bench: lineup.bench, captain: p.id, vice_captain: vice }));
      setMsg(t("nowCaptain", { name: p.last_name, n: lineup.gameweek }));
    } catch (e) { setMsg(e.message); }
  };

  const max = Math.max(1, ...history.map((h) => Number(h.total)));
  const st = squad.standing;
  return (
    <>
      <div className="fx-stats">
        <div><b>{Math.round(squad.total_points)}</b><span>{t("statPoints")}</span></div>
        <div><b>{st ? (t.lang === "fi" ? `${st.rank}.` : `#${st.rank}`) : "-"}</b><span>{t("statFinland")}</span></div>
        <div><b>{last ? Math.round(last.total) : "-"}</b><span>{t("statLastGw")}</span></div>
        <div><b>{squad.bank}</b><span>{t("statBank")}</span></div>
      </div>
      {sponsor && (
        <div className="fx-presented">
          <span>{t("prizesBy")}</span><img src={sponsor.sponsor.logo_url} alt={sponsor.sponsor.name} />
        </div>
      )}
      {!lineup ? <Spinner /> : (
        <section className="fx-section flush">
          <div className="fx-section-head"><h3>{t("lineup", { n: lineup.gameweek })}</h3><span>{t("tapCaptain")}</span></div>
          <Rink lineup={lineup} byId={byId} pointsFor={pointsFor} onPick={makeCaptain} />
          {msg && <p className="fx-toast" onAnimationEnd={() => setMsg("")}>{msg}</p>}
        </section>
      )}
      {history.length > 0 && (
        <section className="fx-section">
          <div className="fx-section-head"><h3>{t("pointsPerGw")}</h3></div>
          <div className="fx-bars">
            {history.map((h) => <div key={h.gameweek} style={{ height: `${(100 * h.total) / max}%` }} title={`GW${h.gameweek}: ${h.total}`}><span>{h.gameweek}</span></div>)}
          </div>
        </section>
      )}
    </>
  );
}

// ------------------------------------------------------------------ page

const TABS = [["team", "tabTeam"], ["coach", "tabCoach"], ["matches", "tabMatches"], ["prizes", "tabPrizes"], ["compete", "tabCompete"]];

/** Lämäri: season-long, free-to-play Liiga fantasy with prizes from Finnish brands. */
export default function Fantasy() {
  const { me } = useAuth();
  const t = useT();
  const navigate = useNavigate();
  const now = useNow();
  const [params, setParams] = useSearchParams();
  const tab = TABS.some(([id]) => id === params.get("tab")) ? params.get("tab") : "team";
  const setTab = (id) => setParams(id === "team" ? {} : { tab: id }, { replace: true });

  const [season, setSeason] = useState(null);
  const [players, setPlayers] = useState([]);
  const [fixtures, setFixtures] = useState([]);
  const [rewards, setRewards] = useState([]);
  const [squad, setSquad] = useState(undefined); // undefined = loading, null = no team yet
  const [leagues, setLeagues] = useState([]);
  const [match, setMatch] = useState(null);
  const [error, setError] = useState("");
  // The Lämäri screen shows on the first visit of a session, for at least SPLASH_MS.
  const [splash, setSplash] = useState(() => { try { return !sessionStorage.getItem(SPLASH_KEY); } catch { return true; } });
  const [minTimeUp, setMinTimeUp] = useState(!splash);

  useEffect(() => {
    if (!splash) return undefined;
    const t = setTimeout(() => setMinTimeUp(true), SPLASH_MS);
    return () => clearTimeout(t);
  }, [splash]);

  useEffect(() => {
    const c = loadFantasy();
    const use = ({ stale, promise }, set, onError) => { if (stale !== undefined) set(stale); promise.then(set, onError || (() => {})); };
    use(c.season, (s) => {
      if (!s) return;
      setSeason(s);
      if (s.next_deadline_gameweek) {
        const f = cached(`fixtures:${s.next_deadline_gameweek}`, () => getFixtures(s.next_deadline_gameweek), 10 * 60e3);
        use(f, (x) => x && setFixtures(x));
      }
    }, (e) => setError(e.message));
    use(c.players, (list) => { if (list) { setPlayers(list); warmPhotos(list.map(photoOf)); } });
    use(c.rewards, (r) => r && setRewards(r));
    use(c.squad, setSquad, () => setSquad(null));
    use(c.leagues, (l) => l && setLeagues(l));
  }, []);

  const ready = season && squad !== undefined && players.length > 0;
  useEffect(() => {
    if (splash && ready && minTimeUp) {
      try { sessionStorage.setItem(SPLASH_KEY, "1"); } catch { /* ignore */ }
      const t = setTimeout(() => setSplash(false), 350); // let the fade finish
      return () => clearTimeout(t);
    }
    return undefined;
  }, [splash, ready, minTimeUp]);

  const byId = useMemo(() => Object.fromEntries([...players, ...(squad?.players || [])].map((p) => [p.id, p])), [players, squad]);
  const mine = useMemo(() => new Set((squad?.players || []).map((p) => p.id)), [squad]);
  const nextGw = season?.gameweeks.find((g) => g.number === season.next_deadline_gameweek);
  const locks = nextGw && countdown(nextGw.deadline, now, t.lang);
  const gwSponsor = rewards.find((r) => r.kind === "rank" && r.period === "week" && r.scope === "global" && r.rank_from === 1);
  const adSponsor = rewards.find((r) => r.kind === "player") || gwSponsor;

  if (splash) return <Splash leaving={ready && minTimeUp} />;

  return (
    <main className="fx">
      <header className="fx-header">
        <button type="button" className="fx-back" onClick={() => navigate("/profile")} aria-label={t("backToProfile")}><ChevronLeft size={22} /></button>
        <div className="fx-brand"><b>LÄMÄRI</b><small>{t("season", { season: season?.name || "" })}</small></div>
        {squad?.standing && <TierBadge tier={squad.standing.tier} />}
      </header>

      <div className="fx-body">
        {error && <div className="error">{error}</div>}
        {!ready ? <Spinner /> : (
          <>
            <div className="fx-section-head"><h3>{t("gameweek", { n: season.next_deadline_gameweek })}</h3>{locks && <span className="fx-lock">{t("locksIn", { left: locks })}</span>}</div>
            <MatchCarousel fixtures={fixtures} now={now} onOpen={setMatch} />

            {squad === null ? (
              <SquadBuilder season={season} players={players} onCreated={(s) => { forget("squad"); setSquad(s); }} />
            ) : (
              <>
                <div className="fx-teamname"><b>{squad.name}</b><small>@{squad.manager}</small></div>
                <nav className="fx-tabs" aria-label="Lämäri">
                  {TABS.map(([id, label]) => <button key={id} type="button" className={tab === id ? "on" : ""} onClick={() => setTab(id)}>{t(label)}</button>)}
                </nav>
                {tab === "team" && <MyTeam squad={squad} byId={byId} sponsor={gwSponsor} />}
                {tab === "coach" && <Coach />}
                {tab === "matches" && <Matches season={season} sponsor={adSponsor} />}
                {tab === "prizes" && <Prizes rewards={rewards} squad={squad} nextGw={nextGw} />}
                {tab === "compete" && <Compete season={season} leagues={leagues} setLeagues={setLeagues} me={me} rewards={rewards} />}
              </>
            )}
          </>
        )}
      </div>
      {match && <MatchSheet fixture={match} players={players} mine={mine} onClose={() => setMatch(null)} />}
      {ready && <Chat startOpen={params.get("chat") === "1"} />}
    </main>
  );
}
