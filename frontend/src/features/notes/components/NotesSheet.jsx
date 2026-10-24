import { BadgeCheck, ExternalLink, Languages, NotebookPen, ThumbsDown, ThumbsUp, X } from "lucide-react";
import { useEffect, useState } from "react";

import { getPostNotes, rateNote, writeNote } from "../api";
import { languageName } from "@/lib/i18n";

const GOOD_TAGS = [
  ["clear_sources", "Cites good sources"],
  ["important_context", "Gives important context"],
  ["relevant", "Directly about the post"],
  ["unbiased", "Neutral language"],
];
const BAD_TAGS = [
  ["missing_sources", "Sources missing or unreliable"],
  ["biased_language", "Opinion or biased"],
  ["outdated", "Outdated"],
  ["off_topic", "Not about the post"],
  ["hard_to_understand", "Hard to understand"],
];
const STATUS = {
  helpful: ["shown", "Shown on the post"],
  needs_more_ratings: ["pending", "Needs more ratings"],
  not_helpful: ["hidden", "Not shown: rated not helpful"],
};

const host = (url) => { try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return url; } };

/** One note: its status, text (in your language when translated) and the rating flow. */
function Note({ note, onRated }) {
  const [original, setOriginal] = useState(false);
  const [choice, setChoice] = useState(null);
  const [tags, setTags] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const t = note.translation && !original ? note.translation : null;
  const [cls, label] = STATUS[note.status] || STATUS.needs_more_ratings;
  const canRate = !note.is_mine && !note.my_rating && note.status === "needs_more_ratings";

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      await rateNote(note.id, choice, tags);
      onRated();
    } catch (e) {
      setError(Object.values(e.data || {}).flat()[0] || e.message);
    } finally {
      setBusy(false);
    }
  };
  const tagSet = choice === "not_helpful" ? BAD_TAGS : GOOD_TAGS;

  return (
    <li className="note-item">
      <div className="note-top">
        <span className={`note-status ${cls}`}>{cls === "shown" && <BadgeCheck size={13} />} {label}</span>
        {note.is_mine && <span className="note-mine">Your note</span>}
        <span className="note-count">{note.rating_count} {note.rating_count === 1 ? "rating" : "ratings"}</span>
      </div>
      <p className="note-claim" dir="auto">{t ? t.claim_summary : note.claim_summary}</p>
      <p className="note-context" dir="auto">{t ? t.context : note.context}</p>
      <div className="note-links">
        {note.citation_urls.map((u) => (
          <a key={u} href={u} target="_blank" rel="noopener noreferrer"><ExternalLink size={12} /> {host(u)}</a>
        ))}
        {note.translation && (
          <button onClick={() => setOriginal(!original)}>
            <Languages size={12} /> {original ? `Show in ${languageName(note.translation.language)}` : "Translated · Original"}
          </button>
        )}
      </div>

      {note.my_rating && <div className="note-rated">You rated this note {note.my_rating.replace("_", " ")}.</div>}
      {canRate && (
        <div className="note-rate">
          <div className="note-q">Is this note helpful?</div>
          <div className="note-choices">
            <button className={choice === "helpful" ? "on" : ""} onClick={() => { setChoice("helpful"); setTags([]); }}><ThumbsUp size={15} /> Yes</button>
            <button className={choice === "somewhat_helpful" ? "on" : ""} onClick={() => { setChoice("somewhat_helpful"); setTags([]); }}>Somewhat</button>
            <button className={choice === "not_helpful" ? "on no" : ""} onClick={() => { setChoice("not_helpful"); setTags([]); }}><ThumbsDown size={15} /> No</button>
          </div>
          {choice && (
            <>
              <div className="note-q small">{choice === "not_helpful" ? "What's wrong with it?" : "What's good about it?"} (pick at least one)</div>
              <div className="note-tags">
                {tagSet.map(([key, text]) => (
                  <button key={key} className={tags.includes(key) ? "on" : ""}
                    onClick={() => setTags((x) => (x.includes(key) ? x.filter((k) => k !== key) : [...x, key]))}>{text}</button>
                ))}
              </div>
              {error && <div className="error">{error}</div>}
              <button className="note-submit" disabled={busy || !tags.length} onClick={submit}>Rate note</button>
            </>
          )}
        </div>
      )}
    </li>
  );
}

/** Write a note: what's misleading or missing, the context, and a source. */
function NoteForm({ postId, onDone, onCancel }) {
  const [claim, setClaim] = useState("");
  const [context, setContext] = useState("");
  const [source, setSource] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const ok = claim.trim() && context.trim().length >= 20 && /^https?:\/\/\S+\.\S+/.test(source.trim());

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      await writeNote(postId, { claim_summary: claim.trim(), context: context.trim(), citation_urls: [source.trim()] });
      onDone();
    } catch (e) {
      setError(e.data ? Object.values(e.data).flat()[0] : e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="note-form">
      <label>What's misleading or missing?</label>
      <input value={claim} maxLength={500} dir="auto" onChange={(e) => setClaim(e.target.value)}
        placeholder="e.g. The bus timetable didn't change" />
      <label>Add context</label>
      <textarea rows={4} value={context} maxLength={2000} dir="auto" onChange={(e) => setContext(e.target.value)}
        placeholder="Explain what readers should know, neutrally and in your own words." />
      <label>Source</label>
      <input value={source} type="url" onChange={(e) => setSource(e.target.value)} placeholder="https://…" />
      <p className="note-hint">Notes are anonymous. Yours is shown once members in different situations rate it helpful.</p>
      {error && <div className="error">{error}</div>}
      <div className="note-form-actions">
        <button className="note-cancel" onClick={onCancel}>Cancel</button>
        <button className="note-submit" disabled={busy || !ok} onClick={submit}>Add note</button>
      </div>
    </div>
  );
}

/** Bottom sheet with a post's Community Notes. */
export default function NotesSheet({ post, onClose, onChanged }) {
  const [notes, setNotes] = useState(null);
  const [writing, setWriting] = useState(false);
  const [error, setError] = useState("");

  const load = () => getPostNotes(post.id).then((d) => setNotes(Array.isArray(d) ? d : d.results || [])).catch((e) => setError(e.message));
  useEffect(() => { load(); }, [post.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const changed = () => { load(); onChanged?.(); };

  return (
    <div className="tt-sheet notes-sheet" role="dialog" aria-label="Community notes">
      <div className="comments-head">
        <h3><NotebookPen size={18} style={{ verticalAlign: -3 }} /> Community notes</h3>
        <button onClick={onClose} aria-label="Close"><X size={22} /></button>
      </div>
      <p className="note-intro">Members add context to posts that may be misleading. A note appears on the post when people in different situations rate it helpful.</p>
      {writing ? (
        <NoteForm postId={post.id} onCancel={() => setWriting(false)} onDone={() => { setWriting(false); changed(); }} />
      ) : (
        <>
          <ul className="notes-list">
            {notes === null && !error && <li className="comments-empty">Loading…</li>}
            {notes?.length === 0 && <li className="comments-empty">No notes yet. If something in this post is misleading, add context.</li>}
            {notes?.map((n) => <Note key={n.id} note={n} onRated={changed} />)}
          </ul>
          {error && <div className="error">{error}</div>}
          {!post.is_mine && (
            <button className="note-write" onClick={() => setWriting(true)}><NotebookPen size={16} /> Write a note</button>
          )}
        </>
      )}
    </div>
  );
}
