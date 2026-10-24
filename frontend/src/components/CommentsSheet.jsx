import { Heart, Languages, Send, X } from "lucide-react";
import { useEffect, useState } from "react";

import { getReplies, likePost, replyToPost } from "../lib/api";
import { useAuth } from "../lib/auth";
import { languageName, timeAgo } from "../lib/i18n";

/** One reply, in the reader's language when a machine translation exists (labelled, original a tap away). */
function Reply({ reply, slug }) {
  const { me } = useAuth();
  const [r, setR] = useState(reply);
  const [original, setOriginal] = useState(false);
  const t = r.translation;
  const like = async () => {
    const res = await likePost(slug, r.id, !r.liked);
    setR({ ...r, liked: res.liked, like_count: res.like_count });
  };
  return (
    <li className="comment">
      <span className="comment-avatar">{(r.author_name || "?").slice(0, 2).toUpperCase()}</span>
      <div className="comment-main">
        <div className="comment-meta"><b>@{r.author_name}</b> · {timeAgo(r.created_at, me?.preferred_language)}</div>
        <p dir="auto">{t && !original ? t.text : r.body}</p>
        {t && (
          <button className="comment-translated" onClick={() => setOriginal(!original)}>
            <Languages size={12} /> {original ? `Show in ${languageName(t.language)}` : `Translated from ${languageName(t.from_language)} · Original`}
          </button>
        )}
        {r.is_mine && r.status === "hidden" && <div className="comment-note">Reported: hidden from others until a moderator reviews it.</div>}
      </div>
      <button className={`comment-like${r.liked ? " active" : ""}`} onClick={like} aria-label="Like reply">
        <Heart size={16} fill={r.liked ? "currentColor" : "none"} />
        <span>{r.like_count || ""}</span>
      </button>
    </li>
  );
}

/** Bottom sheet with a post's replies and a box to add one. */
export default function CommentsSheet({ post, onClose, onReplied }) {
  const [replies, setReplies] = useState(null);
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getReplies(post.community_slug, post.id)
      .then((d) => setReplies(Array.isArray(d) ? d : d.results || []))
      .catch((e) => setError(e.message));
  }, [post.id, post.community_slug]);

  const send = async () => {
    if (!body.trim()) return;
    setBusy(true);
    setError("");
    try {
      const reply = await replyToPost(post.community_slug, post.id, body.trim());
      setReplies((list) => [...(list || []), reply]);
      setBody("");
      onReplied?.();
    } catch (e) {
      setError(Object.values(e.data || {}).flat()[0] || e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="tt-sheet comments-sheet" role="dialog" aria-label="Comments">
      <div className="comments-head">
        <h3>{replies ? `${replies.length} ${replies.length === 1 ? "comment" : "comments"}` : "Comments"}</h3>
        <button onClick={onClose} aria-label="Close"><X size={22} /></button>
      </div>
      <ul className="comments-list">
        {replies === null && !error && <li className="comments-empty">Loading…</li>}
        {replies?.length === 0 && <li className="comments-empty">No comments yet. Be the first.</li>}
        {replies?.map((r) => <Reply key={r.id} reply={r} slug={post.community_slug} />)}
      </ul>
      {error && <div className="error">{error}</div>}
      <div className="comments-input">
        <input value={body} onChange={(e) => setBody(e.target.value)} placeholder="Add a comment…" maxLength={1000} dir="auto"
          onKeyDown={(e) => e.key === "Enter" && send()} />
        <button onClick={send} disabled={busy || !body.trim()} aria-label="Send"><Send size={18} /></button>
      </div>
      <p className="comments-hint">Be kind. Comments are visible to the community and can be reported.</p>
    </div>
  );
}
