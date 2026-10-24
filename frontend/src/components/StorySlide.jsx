import { Bookmark, Heart, Info, Languages, Share2, Volume2, VolumeX } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { interact } from "../lib/api";
import { useAuth } from "../lib/auth";
import { languageName, timeAgo, topicIcon, topicLabel } from "../lib/i18n";
import { useListen } from "./ListenPlayer";

// Background gradients per slide, cycling: dark teal into the brand orange.
const BACKDROPS = [
  "linear-gradient(160deg, #0e2f2f 0%, #1c4a47 45%, #b7743f 100%)",
  "linear-gradient(200deg, #123b3a 0%, #24413f 50%, #e8833a 100%)",
  "linear-gradient(170deg, #10302f 0%, #3d4a3a 55%, #c9662c 100%)",
];

function Rail({ children }) {
  return <div className="tt-rail">{children}</div>;
}

function RailButton({ icon: Icon, label, active, onClick, count }) {
  return (
    <button className={`tt-rail-btn${active ? " active" : ""}`} onClick={onClick} aria-label={label}>
      <span className="tt-rail-icon"><Icon size={26} fill={active ? "currentColor" : "none"} strokeWidth={1.8} /></span>
      <span className="tt-rail-label">{count ?? label}</span>
    </button>
  );
}

/** One full-screen story in the For You feed. */
export default function StorySlide({ card: initial, index }) {
  const { me } = useAuth();
  const [card, setCard] = useState(initial);
  const [panel, setPanel] = useState(null); // "why" | "original" | null
  const ref = useRef(null);
  const listen = useListen([card.headline, card.summary, card.for_you || ""].join(". "), card.language);
  const Icon = topicIcon(card.tags?.[0]);

  // Seen for a moment = a view; still on screen after 6 s = read through (ranking signals).
  useEffect(() => {
    let timer;
    const io = new IntersectionObserver(([e]) => {
      clearTimeout(timer);
      if (!e.isIntersecting) return;
      interact(card.id, "view").catch(() => {});
      timer = setTimeout(() => interact(card.id, "read_through").catch(() => {}), 6000);
    }, { threshold: 0.7 });
    io.observe(ref.current);
    return () => { io.disconnect(); clearTimeout(timer); };
  }, [card.id]);

  const toggle = async (kind, field) => {
    const res = await interact(card.id, card[field] ? `un${kind}` : kind);
    const delta = res.active ? 1 : -1;
    setCard({ ...card, [field]: res.active, metrics: { ...card.metrics, [`${kind}s`]: (card.metrics?.[`${kind}s`] || 0) + delta } });
  };
  const share = async () => {
    const url = `${window.location.origin}/story/${card.id}`;
    if (navigator.share) await navigator.share({ title: card.headline, url }).catch(() => {});
    else await navigator.clipboard?.writeText(url);
    interact(card.id, "share").catch(() => {});
  };
  const source = card.source_urls?.[0] ? new URL(card.source_urls[0]).hostname.replace(/^www\./, "") : "newsroom";
  const j = card.ranking?.jev;

  return (
    <section ref={ref} className="tt-slide" style={{ background: card.image_url ? "#000" : BACKDROPS[index % BACKDROPS.length] }} dir="auto">
      {card.image_url ? <img className="tt-bg-img" src={card.image_url} alt="" /> : <Icon className="tt-bg-icon" size={220} strokeWidth={0.8} />}
      <div className="tt-shade" />

      <Rail>
        <Link to={`/story/${card.id}`} state={card} className="tt-avatar" aria-label="Open story">{source.slice(0, 1).toUpperCase()}</Link>
        <RailButton icon={Heart} label="Like" active={card.liked} count={card.metrics?.likes || 0} onClick={() => toggle("like", "liked")} />
        <RailButton icon={Bookmark} label="Save" active={card.bookmarked} onClick={() => toggle("bookmark", "bookmarked")} />
        <RailButton icon={Share2} label="Share" onClick={share} />
        {listen.supported && <RailButton icon={listen.playing ? VolumeX : Volume2} label={listen.playing ? "Stop" : "Listen"} onClick={listen.toggle} />}
        <RailButton icon={Info} label="Why?" active={panel === "why"} onClick={() => setPanel(panel === "why" ? null : "why")} />
      </Rail>

      <div className="tt-caption">
        <div className="tt-meta">
          <b>@{source}</b> · {timeAgo(card.published_at, me?.preferred_language)}
          {!card.in_your_language && card.requested_language && <span className="tt-badge">Not yet in {languageName(card.requested_language)}</span>}
        </div>
        <Link to={`/story/${card.id}`} state={card}><h2 className="tt-headline">{card.headline}</h2></Link>
        <p className="tt-summary">{card.summary}</p>
        {card.for_you && <p className="tt-foryou"><b>For you:</b> {card.for_you}</p>}

        {panel === "why" && (
          <div className="tt-panel">
            {j ? <>Shown to you because it affects you <b>{Math.round(j.affects_reader * 100)}%</b>, matches your interests <b>{Math.round(j.matches_interests * 100)}%</b>{j.needs_action > 0.5 ? ", and there's something you can act on" : ""}.</>
              : <>Ranked by your interests, your community and how fresh it is.</>}
            <div className="tt-disclosure">AI-assisted, reviewed by {card.ai_disclosure?.reviewer || "an editor"}{card.ai_disclosure?.machine_translated ? ", machine-translated" : ""}.</div>
          </div>
        )}
        {panel === "original" && card.original && (
          <div className="tt-panel" lang={card.original.language}><b>{card.original.headline}</b><br />{card.original.summary}</div>
        )}

        <div className="tt-tags">
          {(card.tags || []).slice(0, 3).map((t) => <span key={t}>#{topicLabel(t).replace(/\s/g, "")}</span>)}
          {card.original && (
            <button className="tt-chip" onClick={() => setPanel(panel === "original" ? null : "original")}>
              <Languages size={14} /> {panel === "original" ? "Hide original" : "Original (Suomi)"}
            </button>
          )}
        </div>
      </div>
    </section>
  );
}
