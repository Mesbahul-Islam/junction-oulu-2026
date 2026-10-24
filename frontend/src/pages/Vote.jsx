import { ChevronLeft, ExternalLink, Languages, Newspaper, ThumbsUp } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { Spinner } from "../components/Spinner";
import { getShortlist, voteStory } from "../lib/api";
import { languageName } from "../lib/i18n";

/** One shortlisted story: its title in the reader's language (original a tap away) and a vote button. */
function Candidate({ item, onVote }) {
  const [original, setOriginal] = useState(false);
  return (
    <div className={`vote-card${item.voted ? " voted" : ""}`}>
      {item.image_url && <img className="vote-img" src={item.image_url} alt="" loading="lazy" referrerPolicy="no-referrer" onError={(e) => { e.currentTarget.style.display = "none"; }} />}
      <div className="vote-main">
        <div className="vote-title" dir="auto">{original ? item.original_title : item.title}</div>
        {item.translated && (
          <button className="vote-meta" onClick={() => setOriginal(!original)}>
            <Languages size={12} /> {original ? `Show in ${languageName(item.language)}` : "Translated from Finnish · Original"}
          </button>
        )}
        <a className="vote-meta" href={item.url} target="_blank" rel="noopener noreferrer"><ExternalLink size={12} /> Kaleva</a>
      </div>
      <button className="vote-btn" onClick={() => onVote(item)} aria-pressed={item.voted} aria-label={item.voted ? "Take back vote" : "Vote"}>
        <ThumbsUp size={20} fill={item.voted ? "currentColor" : "none"} />
        <span>{item.votes}</span>
      </button>
    </div>
  );
}

/** "What should we cover next?": members vote on the newsroom's shortlist. Votes count in the next run. */
export default function Vote() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => { getShortlist().then(setData).catch((e) => setError(e.message)); }, []);

  const vote = async (item) => {
    try {
      const res = await voteStory(item.id, !item.voted);
      setData((d) => ({ ...d, open: d.open.map((x) => (x.id === item.id ? { ...x, votes: res.votes, voted: res.voted } : x)) }));
    } catch (e) {
      setError(Object.values(e.data || {}).flat()[0] || e.message);
    }
  };

  return (
    <main className="screen">
      <div className="back-row">
        <button className="avatar" onClick={() => navigate(-1)} aria-label="Back"><ChevronLeft size={22} /></button>
        <h1>Your newsroom</h1>
      </div>
      <h2 className="title-serif">What should we cover next?</h2>
      <p className="lead" style={{ fontSize: 14 }}>
        These stories are waiting. Vote for the ones that matter to you: the newsroom writes up the most-wanted ones
        in its next run, explained and translated for you. Every group's votes count, however small the group.
      </p>
      {error && <div className="error">{error}</div>}
      {!data ? <Spinner /> : (
        <>
          {!data.member && <div className="error">Join a community to vote. <Link to="/communities" className="btn-link">Find communities</Link></div>}
          {data.open.length ? (
            <div className="vote-list">{data.open.map((item) => <Candidate key={item.id} item={item} onVote={vote} />)}</div>
          ) : <p className="lead">Nothing to vote on yet. New stories arrive after the newsroom's next run.</p>}

          {data.covered.length > 0 && (
            <>
              <div className="section-title">You voted, we covered it</div>
              <div className="vote-list">
                {data.covered.map((item) => (
                  <div key={item.id} className="vote-card covered">
                    <Newspaper size={20} />
                    <div className="vote-main">
                      <div className="vote-title" dir="auto">{item.title}</div>
                      <div className="vote-meta">{item.votes} {item.votes === 1 ? "vote" : "votes"} · {item.story ? "published" : "being reviewed by editors"}</div>
                    </div>
                    {item.story && <Link className="vote-read" to={`/story/${item.story}`}>Read</Link>}
                  </div>
                ))}
              </div>
            </>
          )}
        </>
      )}
    </main>
  );
}
