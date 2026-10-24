import { ArrowLeft, Plus, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import NewsCard from "../components/NewsCard";
import PostSlide from "../components/PostSlide";
import { Spinner } from "../components/Spinner";
import StorySlide from "../components/StorySlide";
import { getCommunityNews, getFeed } from "../lib/api";

const TABS = [
  { id: "community", label: "Community News" },
  { id: "foryou", label: "For You" },
];

/** Home. For You = reviewed news ranked for you, shown two photo cards per screen;
 *  tapping one opens the full-screen swipe view from that story onwards (?story=<id>).
 *  Community News = posts written by members of your communities (full-screen swipe). */
export default function Feed() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") === "community" ? "community" : "foryou";
  const [stories, setStories] = useState(null);
  const [posts, setPosts] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setError("");
    if (tab === "foryou" && stories === null) getFeed({ limit: 30 }).then((d) => setStories(d.results), (e) => setError(e.message));
    if (tab === "community" && posts === null) {
      getCommunityNews().then((d) => setPosts(Array.isArray(d) ? d : d.results || []), (e) => setError(e.message));
    }
  }, [tab, stories, posts]);

  const items = tab === "foryou" ? stories : posts;

  // Swipe view: open on the tapped story and keep going through the ones after it.
  const openId = params.get("story");
  const openIndex = openId && stories ? stories.findIndex((c) => String(c.id) === openId) : -1;
  if (tab === "foryou" && openIndex >= 0) {
    return (
      <main className="tt-feed-wrap">
        <button className="tt-back" aria-label="Back to all news" onClick={() => setParams({}, { replace: true })}>
          <ArrowLeft size={24} />
        </button>
        <div className="tt-feed">
          {stories.slice(openIndex).map((c, i) => <StorySlide key={c.id} card={c} index={openIndex + i} />)}
        </div>
      </main>
    );
  }

  // Overview: stories grouped in twos, one pair per screen.
  const pairs = [];
  for (let i = 0; i < (stories?.length || 0); i += 2) pairs.push(stories.slice(i, i + 2));

  return (
    <main className="tt-feed-wrap">
      <nav className="tt-tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} className={tab === t.id ? "on" : ""}
            onClick={() => setParams(t.id === "foryou" ? {} : { tab: t.id }, { replace: true })}>
            {t.label}
          </button>
        ))}
      </nav>

      <div className="tt-feed" key={tab}>
        {error && <div className="tt-empty">{error}</div>}
        {!error && items === null && <div className="tt-empty"><Spinner /></div>}
        {items?.length === 0 && (
          <div className="tt-empty">
            {tab === "foryou" ? (
              <p>No reviewed stories yet.<br />Editors publish new ones through the day.</p>
            ) : (
              <>
                <p>No posts in your communities yet.</p>
                <Link to="/create" className="tt-cta"><Plus size={18} /> Write the first one</Link>
                <Link to="/communities" className="tt-cta" style={{ marginTop: 10 }}><Users size={18} /> Find communities</Link>
              </>
            )}
          </div>
        )}
        {tab === "foryou" && pairs.map((pair, p) => (
          <section key={pair[0].id} className="tt-pair">
            {pair.map((c, i) => <NewsCard key={c.id} card={c} index={p * 2 + i} onOpen={() => setParams({ story: c.id })} />)}
          </section>
        ))}
        {tab === "community" && posts?.map((p) => (
          <PostSlide key={p.id} post={p} onFlagged={(id) => setPosts((list) => list.filter((x) => x.id !== id))} />
        ))}
      </div>
    </main>
  );
}
