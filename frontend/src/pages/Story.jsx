import { Bookmark, ChevronLeft, Flag, Heart, Share2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import { PlayButton, useListen, Waveform } from "../components/ListenPlayer";
import { Spinner } from "../components/Spinner";
import { getStory, interact, reportStory } from "../lib/api";
import { useAuth } from "../lib/auth";
import { languageName, timeAgo, topicIcon, topicLabel } from "../lib/i18n";

function Meter({ label, value, max = 1 }) {
  return (
    <div className="meter">
      <span>{label}</span>
      <span className="track"><span className="fill" style={{ width: `${Math.round((value / max) * 100)}%`, display: "block" }} /></span>
      <span>{max === 1 ? `${Math.round(value * 100)}%` : `${value.toFixed(1)}/${max}`}</span>
    </div>
  );
}

export default function Story() {
  const { id } = useParams();
  const { me } = useAuth();
  const navigate = useNavigate();
  const { state } = useLocation(); // the feed card, if we came from the feed (has the ranking)
  const [card, setCard] = useState(null);
  const [error, setError] = useState("");
  const [showOriginal, setShowOriginal] = useState(false);
  const endRef = useRef(null);

  useEffect(() => {
    getStory(id).then(setCard, (e) => setError(e.message));
    interact(id, "view").catch(() => {});
  }, [id]);

  // Reaching the end of the story counts as reading it through (a ranking signal).
  useEffect(() => {
    if (!card || !endRef.current) return;
    const io = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) { interact(id, "read_through").catch(() => {}); io.disconnect(); }
    }, { threshold: 1 });
    io.observe(endRef.current);
    return () => io.disconnect();
  }, [card, id]);

  const text = card ? [card.headline, card.summary, ...(card.key_facts || []), card.for_you || ""].join(". ") : "";
  const listen = useListen(text, card?.language || "en");

  if (error) return <main className="screen"><div className="error">{error}</div></main>;
  if (!card) return <Spinner />;

  const toggle = async (kind) => {
    const active = card[kind === "like" ? "liked" : "bookmarked"];
    const res = await interact(id, active ? `un${kind}` : kind);
    setCard({ ...card, [kind === "like" ? "liked" : "bookmarked"]: res.active });
  };
  const share = async () => {
    const url = window.location.href;
    if (navigator.share) await navigator.share({ title: card.headline, url }).catch(() => {});
    else await navigator.clipboard?.writeText(url);
    interact(id, "share").catch(() => {});
  };
  const report = async () => {
    const body = window.prompt("What is wrong or outdated in this story?");
    if (body === null) return;
    await reportStory(id, body);
    window.alert("Thanks. An editor will check it; the story is paused until then.");
    navigate("/");
  };

  const Icon = topicIcon(card.tags?.[0]);
  const ranking = state?.ranking || card.ranking;
  const ai = card.ai_disclosure || {};

  return (
    <main className="screen" dir="auto">
      <div className="story-media">
        <div className="floating">
          <button className="icon-btn glass" onClick={() => navigate(-1)} aria-label="Back"><ChevronLeft size={22} /></button>
          <button className={`icon-btn glass${card.liked ? " active" : ""}`} onClick={() => toggle("like")} aria-label="Like">
            <Heart size={20} fill={card.liked ? "currentColor" : "none"} />
          </button>
        </div>
        {card.image_url ? <img src={card.image_url} alt="" referrerPolicy="no-referrer" onError={(e) => { e.currentTarget.style.display = "none"; }} style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }} />
          : <Icon size={72} strokeWidth={1.2} style={{ opacity: 0.5, position: "absolute" }} />}
        <PlayButton listen={listen} />
      </div>
      <Waveform listen={listen} />

      <div className="story-actions">
        <span className="chip">{timeAgo(card.published_at, me.preferred_language)}</span>
        <div style={{ display: "flex", gap: 8 }}>
          <button className={`icon-btn glass${card.bookmarked ? " active" : ""}`} onClick={() => toggle("bookmark")} aria-label="Save">
            <Bookmark size={20} fill={card.bookmarked ? "currentColor" : "none"} />
          </button>
          <button className="icon-btn glass" onClick={share} aria-label="Share"><Share2 size={20} /></button>
        </div>
      </div>

      <h1 className="story-title">{card.headline}</h1>
      <p className="story-summary">{card.summary}</p>

      {!card.in_your_language && card.requested_language && (
        <div className="block highlight">
          <p>Not yet available in {languageName(card.requested_language)}. Showing {languageName(card.language)} until a reviewer approves the translation.</p>
        </div>
      )}

      {card.for_you && (
        <div className="block highlight">
          <h4>What this means for you</h4>
          <p>{card.for_you}</p>
        </div>
      )}

      {card.key_facts?.length > 0 && (
        <div className="block">
          <h4>Key facts</h4>
          <ul>{card.key_facts.map((f) => <li key={f}>{f}</li>)}</ul>
        </div>
      )}

      {card.background && (
        <div className="block"><h4>Background</h4><p>{card.background}</p></div>
      )}

      {card.original && (
        <div className="block">
          <h4>Original ({languageName(card.original.language)})</h4>
          {showOriginal ? (
            <div lang={card.original.language}>
              <p style={{ fontWeight: 600 }}>{card.original.headline}</p>
              <p>{card.original.summary}</p>
              {card.original.key_facts?.length > 0 && <ul>{card.original.key_facts.map((f) => <li key={f}>{f}</li>)}</ul>}
            </div>
          ) : (
            <button className="text-btn" onClick={() => { setShowOriginal(true); interact(id, "expand").catch(() => {}); }}>
              Show the Finnish original
            </button>
          )}
        </div>
      )}

      {ranking?.ranker === "jev" && (
        <div className="block">
          <h4>Why you're seeing this</h4>
          <Meter label="Affects you" value={ranking.jev.affects_reader} />
          <Meter label="Your interests" value={ranking.jev.matches_interests} />
          <Meter label="Action needed" value={ranking.jev.needs_action} />
          <Meter label="Urgency" value={ranking.jev.urgency} max={3} />
        </div>
      )}

      {card.community_notes?.map((n) => (
        <div key={n.id} className="block"><h4>Community note</h4><p>{n.claim_summary}: {n.context}</p></div>
      ))}
      {card.correction_note && <div className="block"><h4>Correction</h4><p>{card.correction_note}</p></div>}

      <div className="meta-row" style={{ color: "rgba(255,255,255,0.8)" }}>
        {(card.tags || []).map((t) => <span key={t} className="tag-chip">{topicLabel(t)}</span>)}
      </div>
      <p className="disclosure">
        AI-assisted{ai.machine_translated ? " and machine-translated" : ""}, reviewed by {ai.reviewer || "an editor"}
        {ai.verified_at ? ` on ${new Date(ai.verified_at).toLocaleDateString(me.preferred_language)}` : ""}.{" "}
        Sources: {(card.source_urls || []).map((u, i) => <a key={u} href={u} target="_blank" rel="noreferrer" style={{ textDecoration: "underline" }}>[{i + 1}]</a>)}
      </p>
      <button className="btn-ghost" onClick={report}><Flag size={16} style={{ verticalAlign: -3 }} /> Report wrong or outdated</button>
      <div ref={endRef} style={{ height: 1 }} />
    </main>
  );
}
