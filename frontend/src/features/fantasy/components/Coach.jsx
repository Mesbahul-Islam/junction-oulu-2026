import { ArrowLeftRight, ChevronRight, Crown, Newspaper, Shirt, TrendingUp, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getCoach, getSquadNews } from "@/features/fantasy/api";
import { useT } from "../lib/lamariText";
import { Spinner } from "@/components/ui";
import { Pager, Wording } from "./util";

const TIP_ICON = { captain: Crown, lineup: Shirt, transfer: ArrowLeftRight };
const NEWS_PAGE = 5;

/** A story the desk found, read inside the app while our newsroom prepares its own version. */
function StoryReader({ note, onClose }) {
  const t = useT();
  return (
    <div className="fx-sheet-wrap" onClick={onClose}>
      <div className="fx-sheet" onClick={(e) => e.stopPropagation()}>
        <div className="fx-sheet-head"><span className="fx-news-meta">{note.player.first_name} {note.player.last_name}</span>
          <button type="button" onClick={onClose} aria-label={t("close")}><X size={20} /></button></div>
        <h3 className="fx-reader-title">{note.title}</h3>
        {note.body && <p className="fx-reader-body">{note.body}</p>}
        <p className="fx-note">{t("writingStory")}</p>
        <p className="fx-source">{t("source")}{note.published_at ? `, ${new Date(note.published_at).toLocaleDateString("fi-FI")}` : ""}. <a href={note.url} target="_blank" rel="noreferrer" className="fx-link">{t("original")}</a></p>
      </div>
    </div>
  );
}

function SportsDesk() {
  const t = useT();
  const [page, setPage] = useState(0);
  const [data, setData] = useState(null);
  const [reading, setReading] = useState(null);
  useEffect(() => { getSquadNews(page * NEWS_PAGE, NEWS_PAGE).then(setData, () => setData({ results: [], total: 0 })); }, [page]);
  if (data && !data.results.length) return null;

  return (
    <section className="fx-section">
      <div className="fx-section-head"><h3>{t("news")}</h3></div>
      {!data ? <Spinner /> : (
        <>
          <ul className="fx-news">
            {data.results.map((n) => (
              <li key={n.id}>
                <span className={`fx-news-kind ${n.kind}`}>{n.kind === "news" ? <Newspaper size={14} /> : <TrendingUp size={14} />}</span>
                <div>
                  <div className="fx-news-meta">{n.player.first_name} {n.player.last_name}, {n.source === "kaleva" ? t("kaleva") : t("liigaStats")}</div>
                  {n.story_id ? <Link to={`/story/${n.story_id}`} className="fx-news-title">{n.title} <ChevronRight size={13} /></Link>
                    : n.url ? <button type="button" className="fx-news-title" onClick={() => setReading(n)}>{n.title} <ChevronRight size={13} /></button>
                      : <div className="fx-news-title">{n.title}</div>}
                  {n.kind !== "news" && n.body && <p>{n.body}</p>}
                </div>
              </li>
            ))}
          </ul>
          <Pager page={page} pages={Math.ceil(data.total / NEWS_PAGE)} onPage={setPage} />
        </>
      )}
      {reading && <StoryReader note={reading} onClose={() => setReading(null)} />}
    </section>
  );
}

/** Your last gameweek reviewed and concrete picks for the next one, all built from Liiga data. */
export default function Coach() {
  const t = useT();
  const [data, setData] = useState(null);
  useEffect(() => { getCoach().then(setData, () => setData({ review: [], tips: [] })); }, []);
  if (!data) return <Spinner />;

  return (
    <>
      {data.review.length > 0 && (
        <section className="fx-section">
          <div className="fx-section-head"><h3>{t("review", { n: data.gameweek })}</h3></div>
          <ul className="fx-lines">{data.review.map((r) => <li key={r}>{r}</li>)}</ul>
        </section>
      )}
      {data.tips.length > 0 && (
        <section className="fx-section">
          <div className="fx-section-head"><h3>{t("picks", { n: data.next_gameweek })}</h3></div>
          <ul className="fx-tips">
            {data.tips.map((t) => {
              const Icon = TIP_ICON[t.kind] || Shirt;
              return <li key={t.text}><span className="fx-tip-icon"><Icon size={16} /></span><p>{t.text}</p></li>;
            })}
          </ul>
          <Wording source={data.source} />
        </section>
      )}
      <SportsDesk />
    </>
  );
}
