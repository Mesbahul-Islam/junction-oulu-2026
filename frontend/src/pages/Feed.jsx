import { Plus, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import PostSlide from "../components/PostSlide";
import { Spinner } from "../components/Spinner";
import StorySlide from "../components/StorySlide";
import { getCommunityNews, getFeed } from "../lib/api";

const TABS = [
  { id: "community", label: "Community News" },
  { id: "foryou", label: "For You" },
];

/** TikTok-style home: full-screen vertical feeds. For You = reviewed news ranked for you;
 *  Community News = posts written by members of your communities. */
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
        {tab === "foryou" && stories?.map((c, i) => <StorySlide key={c.id} card={c} index={i} />)}
        {tab === "community" && posts?.map((p) => (
          <PostSlide key={p.id} post={p} onFlagged={(id) => setPosts((list) => list.filter((x) => x.id !== id))} />
        ))}
      </div>
    </main>
  );
}
