import { ArrowRight, Flag, Languages, MessageCircle, Newspaper, Share2, Users } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { flagPost } from "../lib/api";
import { useAuth } from "../lib/auth";
import { languageName, timeAgo } from "../lib/i18n";

const REASONS = [
  { value: "hate", label: "Hate or harassment" },
  { value: "privacy", label: "Violates someone's privacy" },
  { value: "false", label: "False or misleading" },
  { value: "spam", label: "Spam or advertising" },
  { value: "other", label: "Something else" },
];

/**
 * One full-screen community post. Written by a member, not the newsroom: it is labelled so,
 * and anyone can flag it (it's then hidden until a moderator reviews it).
 */
export default function PostSlide({ post, onFlagged }) {
  const { me } = useAuth();
  const [flagging, setFlagging] = useState(false);
  const [done, setDone] = useState("");
  const [showOriginal, setShowOriginal] = useState(false);
  const t = post.translation; // machine translation into the reader's language, if any
  const initials = (post.author_name || "?").slice(0, 2).toUpperCase();

  const flag = async (reason) => {
    const res = await flagPost(post.community_slug, post.id, reason);
    setDone(res.detail);
    setFlagging(false);
    setTimeout(() => onFlagged?.(post.id), 1800);
  };
  const share = async () => {
    if (navigator.share) await navigator.share({ text: post.body }).catch(() => {});
    else await navigator.clipboard?.writeText(post.body);
  };

  return (
    <section className="tt-slide tt-post" dir="auto">
      <MessageCircle className="tt-bg-icon" size={220} strokeWidth={0.8} />
      <div className="tt-shade" />

      <div className="tt-rail">
        <span className="tt-avatar">{initials}</span>
        <button className="tt-rail-btn" onClick={share} aria-label="Share">
          <span className="tt-rail-icon"><Share2 size={26} strokeWidth={1.8} /></span><span className="tt-rail-label">Share</span>
        </button>
        {!post.is_mine && (
          <button className="tt-rail-btn" onClick={() => setFlagging(true)} aria-label="Report post">
            <span className="tt-rail-icon"><Flag size={26} strokeWidth={1.8} /></span><span className="tt-rail-label">Report</span>
          </button>
        )}
      </div>

      <div className="tt-caption">
        <div className="tt-label"><Users size={14} /> Community post · not reviewed by editors</div>
        <div className="tt-meta"><b>@{post.author_name}</b> · {post.community_name} · {timeAgo(post.created_at, me?.preferred_language)}</div>
        <p className="tt-post-body" lang={t && !showOriginal ? t.language : post.language || undefined}>
          {t && !showOriginal ? t.text : post.body}
        </p>
        {t && (
          <button className="tt-chip" style={{ marginTop: 8 }} onClick={() => setShowOriginal(!showOriginal)}>
            <Languages size={14} />
            {showOriginal ? `Show in ${languageName(t.language)}` : `Auto-translated${t.from_language ? ` from ${languageName(t.from_language)}` : ""} · Show original`}
          </button>
        )}
        {post.answered_by && (
          <Link to={`/story/${post.answered_by.snippet}`} className="tt-answer">
            <Newspaper size={18} />
            <span><b>Answered by the newsroom</b><br />{post.answered_by.headline}</span>
            <ArrowRight size={18} />
          </Link>
        )}
        {post.is_mine && post.status === "hidden" && (
          <div className="tt-panel">Your post was reported and is hidden from others until a moderator reviews it.</div>
        )}
        {done && <div className="tt-panel">{done}</div>}
      </div>

      {flagging && (
        <div className="tt-sheet" role="dialog" aria-label="Report this post">
          <h3>Why are you reporting this?</h3>
          <p>The post is hidden right away and a moderator from your community reviews it.</p>
          {REASONS.map((r) => <button key={r.value} className="tt-sheet-option" onClick={() => flag(r.value)}>{r.label}</button>)}
          <button className="tt-sheet-cancel" onClick={() => setFlagging(false)}>Cancel</button>
        </div>
      )}
    </section>
  );
}
