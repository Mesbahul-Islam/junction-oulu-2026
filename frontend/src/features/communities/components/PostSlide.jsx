import { ArrowRight, ExternalLink, Flag, Flame, Heart, Languages, MessageCircle, Newspaper, NotebookPen, Share2, ShieldAlert, Users } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { flagPost, getPost, likePost, sharePost } from "../api";
import { useAuth } from "@/features/auth/AuthProvider";
import { languageName, timeAgo } from "@/lib/i18n";
import CommentsSheet from "./CommentsSheet";
import NotesSheet from "@/features/notes/components/NotesSheet";
import { RailButton } from "@/features/feed/components/StorySlide";
import TrustBadge from "@/features/trust/components/TrustBadge";
import { useTrustedVoices } from "@/features/trust/hooks";

const REASONS = [
  { value: "hate", label: "Hate or harassment" },
  { value: "privacy", label: "Violates someone's privacy" },
  { value: "false", label: "False or misleading" },
  { value: "spam", label: "Spam or advertising" },
  { value: "other", label: "Something else" },
];

const host = (url) => { try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return url; } };

/**
 * One full-screen community post. Written by a member, not the newsroom: it is labelled so.
 * Hot posts are marked; anyone can report one. A "misleading" report asks members for a
 * Community Note (shown as "Readers added context" once rated helpful); other reports hide
 * the post until a moderator reviews it.
 */
export default function PostSlide({ post: initial, onFlagged }) {
  const isTrusted = useTrustedVoices();
  const { me } = useAuth();
  const [post, setPost] = useState(initial);
  const [comments, setComments] = useState(false);
  const [notes, setNotes] = useState(false);
  const [flagging, setFlagging] = useState(false);
  const [done, setDone] = useState("");
  const [showOriginal, setShowOriginal] = useState(false);
  const t = post.translation; // machine translation into the reader's language, if any
  const initials = (post.author_name || "?").slice(0, 2).toUpperCase();

  const flag = async (reason) => {
    const res = await flagPost(post.community_slug, post.id, reason);
    setDone(res.detail);
    setFlagging(false);
    if (res.hidden === false) setPost((p) => ({ ...p, misleading_reports: (p.misleading_reports || 0) + 1 }));
    else setTimeout(() => onFlagged?.(post.id), 1800);
  };
  const refresh = () => getPost(post.community_slug, post.id).then((p) => setPost((old) => ({ ...old, ...p }))).catch(() => {});
  const note = post.community_note;
  const nt = note?.translation && !showOriginal ? note.translation : null;
  const like = async () => {
    const res = await likePost(post.community_slug, post.id, !post.liked);
    setPost((p) => ({ ...p, liked: res.liked, like_count: res.like_count }));
  };
  const share = async () => {
    if (navigator.share) await navigator.share({ text: post.body }).catch(() => {});
    else await navigator.clipboard?.writeText(post.body);
    const res = await sharePost(post.community_slug, post.id).catch(() => null);
    if (res) setPost((p) => ({ ...p, share_count: res.share_count }));
  };

  return (
    <section className="tt-slide tt-post" dir="auto">
      {post.image ? <img className="tt-bg-img" src={post.image} alt="" loading="lazy" /> : <MessageCircle className="tt-bg-icon" size={220} strokeWidth={0.8} />}
      <div className="tt-shade" />

      <div className="tt-rail">
        <span className="tt-avatar">{initials}</span>
        <RailButton icon={Heart} label="Like" active={post.liked} count={post.like_count || 0} onClick={like} />
        <RailButton icon={MessageCircle} label="Comments" count={post.reply_count || 0} onClick={() => setComments(true)} />
        <RailButton icon={Share2} label="Share" count={post.share_count || "Share"} onClick={share} />
        <span className={`notes-rail${post.notes_to_rate ? " due" : ""}`}>
          <RailButton icon={NotebookPen} label="Community notes" count={post.notes_to_rate ? `${post.notes_to_rate} to rate` : "Notes"} onClick={() => setNotes(true)} />
        </span>
        {!post.is_mine && (
          <button className="tt-rail-btn" onClick={() => setFlagging(true)} aria-label="Report post">
            <span className="tt-rail-icon"><Flag size={26} strokeWidth={1.8} /></span><span className="tt-rail-label">Report</span>
          </button>
        )}
      </div>

      <div className="tt-caption">
        {post.hot && <div className="tt-hot"><Flame size={14} /> Trending in {post.community_name}</div>}
        <div className="tt-label"><Users size={14} /> Community post · not reviewed by editors</div>
        {post.image && post.image_status === "pending" && <div className="tt-label photo-pending">Only you can see this photo until a moderator checks it</div>}
        {post.image && post.faces_blurred > 0 && <div className="tt-label">Faces blurred automatically</div>}
        <div className="tt-meta"><b>@{post.author_name}</b>{isTrusted(post.author, post.community_slug) && <TrustBadge />} · {post.community_name} · {timeAgo(post.created_at, me?.preferred_language)}</div>
        <p className="tt-post-body" lang={t && !showOriginal ? t.language : post.language || undefined}>
          {t && !showOriginal ? t.text : post.body}
        </p>
        {t && (
          <button className="tt-chip" style={{ marginTop: 8 }} onClick={() => setShowOriginal(!showOriginal)}>
            <Languages size={14} />
            {showOriginal ? `Show in ${languageName(t.language)}` : `Auto-translated${t.from_language ? ` from ${languageName(t.from_language)}` : ""} · Show original`}
          </button>
        )}
        {note ? (
          <button className="tt-note" onClick={() => setNotes(true)} dir="auto">
            <div className="tt-note-head"><Users size={15} /> Readers added context</div>
            <p className="tt-note-text" lang={nt ? nt.language : note.language || undefined}>{nt ? nt.context : note.context}</p>
            <div className="tt-note-links">
              {note.citation_urls.slice(0, 2).map((u) => <span key={u}><ExternalLink size={11} /> {host(u)}</span>)}
            </div>
            <div className="tt-note-foot">Rated helpful by people in different situations · Rate it</div>
          </button>
        ) : post.misleading_reports > 0 && (
          <button className="tt-misleading" onClick={() => setNotes(true)}>
            <ShieldAlert size={15} /> Readers say this may be misleading · <b>Add context</b>
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

      {comments && (
        <CommentsSheet post={post} onClose={() => setComments(false)}
          onReplied={() => setPost((p) => ({ ...p, reply_count: (p.reply_count || 0) + 1 }))} />
      )}

      {notes && <NotesSheet post={post} onClose={() => setNotes(false)} onChanged={refresh} />}

      {flagging && (
        <div className="tt-sheet" role="dialog" aria-label="Report this post">
          <h3>Why are you reporting this?</h3>
          <p>If it's misleading, it stays up and members are asked to add context. Other reports hide it until a moderator from your community reviews it.</p>
          {REASONS.map((r) => <button key={r.value} className="tt-sheet-option" onClick={() => flag(r.value)}>{r.label}</button>)}
          <button className="tt-sheet-cancel" onClick={() => setFlagging(false)}>Cancel</button>
        </div>
      )}
    </section>
  );
}
