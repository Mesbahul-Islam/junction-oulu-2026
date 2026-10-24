import { useEffect, useState } from "react";

import NewsCard from "../components/NewsCard";
import { Spinner } from "../components/Spinner";
import { getArrival, getFeed, getInterests } from "../lib/api";
import { useAuth } from "../lib/auth";
import { topicIcon } from "../lib/i18n";

const BUCKET_TITLE = { first_48h: "Your first 48 hours", first_week: "Your first week", first_month: "Your first month" };

/** Browse every topic, plus the newcomer sequence for readers who set an arrival date. */
export default function Explore() {
  const { me } = useAuth();
  const [topics, setTopics] = useState([]);
  const [topic, setTopic] = useState(null);
  const [cards, setCards] = useState([]);
  const [arrival, setArrival] = useState(null);

  useEffect(() => {
    getInterests().then((d) => setTopics(Array.isArray(d) ? d : d.results || []));
    if (me.arrival_date) getArrival().then(setArrival).catch(() => {});
  }, [me.arrival_date]);

  useEffect(() => {
    if (!topic) return;
    setCards(null);
    getFeed({ tag: topic.slug }).then((d) => setCards(d.results));
  }, [topic]);

  return (
    <main className="screen">
      <h1 className="title-serif">Explore</h1>
      <p className="lead">Browse local news by topic.</p>

      {arrival?.results?.length > 0 && !topic && (
        <>
          <div className="section-head"><h2>{BUCKET_TITLE[arrival.bucket] || "Getting started in Finland"}</h2></div>
          <div className="card-list" style={{ marginBottom: 24 }}>
            {arrival.results.slice(0, 5).map((c, i) => <NewsCard key={c.id} card={c} index={i} />)}
          </div>
        </>
      )}

      <div className="grid2">
        {topics.map((t) => {
          const Icon = topicIcon(t.slug);
          return (
            <button key={t.slug} className={`choice-card${topic?.slug === t.slug ? " selected" : ""}`}
              onClick={() => setTopic(topic?.slug === t.slug ? null : t)}>
              <span className="icon-circle" style={{ margin: "0 0 10px" }}><Icon size={22} strokeWidth={1.7} /></span>
              <div className="name">{t.name}</div>
            </button>
          );
        })}
      </div>

      {topic && (
        <>
          <div className="section-head" style={{ marginTop: 22 }}><h2>{topic.name}</h2></div>
          {!cards ? <Spinner /> : cards.length ? (
            <div className="card-list">{cards.map((c, i) => <NewsCard key={c.id} card={c} index={i} />)}</div>
          ) : <div className="empty">No {topic.name.toLowerCase()} stories right now.</div>}
        </>
      )}
    </main>
  );
}
