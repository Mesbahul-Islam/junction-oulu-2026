import { ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";
import { Fragment, useEffect, useState } from "react";

import { getAnalysis, getFixtures } from "../../lib/api";
import { useT } from "../../lib/lamariText";
import { Spinner } from "../Spinner";
import { finnishTime, Wording } from "./util";

const seg = (value, set, options) => (
  <div className="fx-seg small">
    {options.map(([v, l]) => <button key={v} type="button" className={value === v ? "on" : ""} onClick={() => set(v)}>{l}</button>)}
  </div>
);

// Remembered across games, so a newcomer doesn't have to switch every time.
const readPref = () => { try { return localStorage.getItem("lamari:reader") || "fan"; } catch { return "fan"; } };

function Analysis({ fixture }) {
  const t = useT();
  const [detail, setDetail] = useState("short");
  const [reader, setReaderState] = useState(readPref);
  const setReader = (v) => { setReaderState(v); try { localStorage.setItem("lamari:reader", v); } catch { /* ignore */ } };
  const [data, setData] = useState(null);
  useEffect(() => { setData(null); getAnalysis(fixture.id, detail, reader).then(setData, () => setData({ notes: [], sections: [] })); }, [fixture.id, detail, reader]);
  return (
    <div className="fx-analysis">
      <div className="fx-analysis-controls">
        {seg(reader, setReader, [["fan", t("fan")], ["new", t("newToHockey")]])}
        {seg(detail, setDetail, [["short", t("short")], ["full", t("full")]])}
      </div>
      {!data ? <Spinner /> : <AnalysisBody data={data} />}
    </div>
  );
}

function AnalysisBody({ data }) {
  return (
    <>
      <ul className="fx-lines">{data.notes.map((n) => <li key={n}>{n}</li>)}</ul>
      {data.sections.map((s) => (
        <div key={s.title} className="fx-analysis-part"><h4>{s.title}</h4><ul className="fx-lines">{s.lines.map((l) => <li key={l}>{l}</li>)}</ul></div>
      ))}
      <Wording source={data.source} />
    </>
  );
}

/** One gameweek of games at a time; tap a game for the analysis (finished) or a preview (upcoming). */
export default function Matches({ season, sponsor }) {
  const t = useT();
  const played = season.gameweeks.filter((g) => g.status !== "upcoming").map((g) => g.number);
  const [gw, setGw] = useState(played[played.length - 1] || season.next_deadline_gameweek);
  const [fixtures, setFixtures] = useState(null);
  const [open, setOpen] = useState(null);
  const numbers = season.gameweeks.map((g) => g.number);

  useEffect(() => { setFixtures(null); setOpen(null); getFixtures(gw).then(setFixtures); }, [gw]);

  return (
    <section className="fx-section">
      <div className="fx-gw-pager">
        <button type="button" aria-label={t("prevGw")} disabled={gw <= numbers[0]} onClick={() => setGw(gw - 1)}><ChevronLeft size={18} /></button>
        <b>{t("gameweek", { n: gw })}</b>
        <button type="button" aria-label={t("nextGw")} disabled={gw >= numbers[numbers.length - 1]} onClick={() => setGw(gw + 1)}><ChevronRight size={18} /></button>
      </div>
      {!fixtures ? <Spinner /> : (
        <ul className="fx-games">
          {fixtures.map((f, i) => (
            <Fragment key={f.id}>
              <li className={open === f.id ? "open" : ""}>
                <button type="button" className="fx-game" onClick={() => setOpen(open === f.id ? null : f.id)}>
                  <span className="fx-team">{f.home.logo_url && <img src={f.home.logo_url} alt="" />}{f.home.name}</span>
                  <span className="fx-score">
                    {f.status === "finished" ? `${f.home_goals}-${f.away_goals}` : f.status === "live" ? t("live") : finnishTime(f.starts_at, t.locale)}
                    {f.finished_type?.includes("EXTENDED") && <small>{t("ot")}</small>}
                    {f.finished_type?.includes("WINNING_SHOT") && <small>{t("so")}</small>}
                  </span>
                  <span className="fx-team right">{f.away.name}{f.away.logo_url && <img src={f.away.logo_url} alt="" />}</span>
                  <ChevronDown size={16} className="fx-caret" />
                </button>
                {open === f.id && <Analysis fixture={f} />}
              </li>
              {i === 2 && sponsor && (
                <li className="fx-ad">
                  <span className="fx-ad-label">{t("sponsored")}</span>
                  <img src={sponsor.sponsor.logo_url} alt={sponsor.sponsor.name} />
                  <p><b>{sponsor.title}.</b> {sponsor.description}</p>
                </li>
              )}
            </Fragment>
          ))}
        </ul>
      )}
    </section>
  );
}
