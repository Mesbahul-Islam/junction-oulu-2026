import { useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, ExternalLink, Languages, NotebookPen } from "lucide-react";
import { useState } from "react";

import { Badge, Button, Field, Input, Textarea, ToggleChips, toast } from "@/components/ui";
import { languageName } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { getPostNotes, rateNote, writeNote } from "../api";

const GOOD_TAGS = [
  { value: "clear_sources", label: "Cites good sources" },
  { value: "important_context", label: "Gives important context" },
  { value: "relevant", label: "Directly about the post" },
  { value: "unbiased", label: "Neutral language" },
];
const BAD_TAGS = [
  { value: "missing_sources", label: "Sources missing or unreliable" },
  { value: "biased_language", label: "Opinion or biased" },
  { value: "outdated", label: "Outdated" },
  { value: "off_topic", label: "Not about the post" },
  { value: "hard_to_understand", label: "Hard to understand" },
];
const VALUES = [
  { value: "helpful", label: "Helpful" },
  { value: "somewhat_helpful", label: "Somewhat" },
  { value: "not_helpful", label: "Not helpful" },
];
const STATUS = {
  helpful: <Badge tone="confirmed"><BadgeCheck size={12} />Shown on the post</Badge>,
  needs_more_ratings: <Badge>Needs more ratings</Badge>,
  not_helpful: <Badge>Not shown: rated not helpful</Badge>,
};
const host = (u) => { try { return new URL(u).hostname.replace(/^www\./, ""); } catch { return u; } };
const firstError = (e) => (e.data && typeof e.data === "object" ? Object.values(e.data).flat()[0] : null) || e.message;

function Note({ note, onChanged }) {
  const [original, setOriginal] = useState(false);
  const [value, setValue] = useState(null);
  const [tags, setTags] = useState([]);
  const [busy, setBusy] = useState(false);
  const t = note.translation && !original ? note.translation : null;
  const canRate = !note.is_mine && !note.my_rating && note.status === "needs_more_ratings";

  const submit = async () => {
    setBusy(true);
    try {
      await rateNote(note.id, value, tags);
      toast({ title: "Thanks for rating", tone: "confirmed" });
      onChanged();
    } catch (e) {
      toast({ title: "Your rating wasn't saved", description: firstError(e), tone: "danger" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className="flex flex-col gap-2 py-4">
      <div className="flex flex-wrap items-center gap-2 text-caption text-muted">
        {STATUS[note.status]}
        {note.is_mine && <Badge appearance="outline">Your note</Badge>}
        <span>{note.rating_count === 1 ? "1 rating" : `${note.rating_count} ratings`}</span>
      </div>
      <p className="text-ui font-medium" dir="auto">{t ? t.claim_summary : note.claim_summary}</p>
      <p className="text-ui text-ink/90" dir="auto">{t ? t.context : note.context}</p>
      <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-caption text-muted">
        {note.citation_urls.map((u) => (
          <a key={u} href={u} target="_blank" rel="noreferrer" className="focus-ring inline-flex items-center gap-1 rounded-control hover:text-ink">
            {host(u)}<ExternalLink size={11} />
          </a>
        ))}
        {note.translation && (
          <button type="button" onClick={() => setOriginal(!original)} className="focus-ring inline-flex items-center gap-1 rounded-control hover:text-ink">
            <Languages size={12} />{original ? `Show in ${languageName(note.translation.language)}` : `Machine-translated from ${languageName(note.translation.from_language)} · show original`}
          </button>
        )}
      </p>
      {note.my_rating && <p className="text-caption text-muted">You rated it {note.my_rating.replace("_", " ")}.</p>}
      {canRate && (
        <div className="mt-1 flex flex-col gap-3 rounded-card bg-sunk/60 p-3">
          <p className="text-meta font-medium">Is this note helpful?</p>
          <div role="radiogroup" aria-label="Rating" className="flex flex-wrap gap-2">
            {VALUES.map((v) => (
              <button
                key={v.value}
                type="button"
                role="radio"
                aria-checked={value === v.value}
                onClick={() => { setValue(v.value); setTags([]); }}
                className={cn(
                  "focus-ring h-8 rounded-control border px-3 text-meta transition-colors [@media(pointer:coarse)]:h-11",
                  value === v.value ? "border-ink bg-ink text-on-ink" : "border-line bg-surface text-ink hover:border-ink/25",
                )}
              >
                {v.label}
              </button>
            ))}
          </div>
          {value && (
            <>
              <p className="text-meta text-muted">{value === "not_helpful" ? "What's wrong with it?" : "What's good about it?"} Pick at least one.</p>
              <ToggleChips value={tags} onValueChange={setTags} options={value === "not_helpful" ? BAD_TAGS : GOOD_TAGS} />
              <div><Button size="sm" onClick={submit} disabled={busy || !tags.length}>Rate note</Button></div>
            </>
          )}
        </div>
      )}
    </li>
  );
}

function NoteForm({ postId, onDone, onCancel }) {
  const [claim, setClaim] = useState("");
  const [context, setContext] = useState("");
  const [source, setSource] = useState("");
  const [busy, setBusy] = useState(false);
  const ok = claim.trim() && context.trim().length >= 20 && /^https?:\/\/\S+\.\S+/.test(source.trim());
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await writeNote(postId, { claim_summary: claim.trim(), context: context.trim(), citation_urls: [source.trim()] });
      toast({ title: "Note added", description: "It's shown once members in different situations rate it helpful.", tone: "confirmed" });
      onDone();
    } catch (err) {
      toast({ title: "Your note wasn't saved", description: firstError(err), tone: "danger" });
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={submit} className="flex flex-col gap-4 rounded-card border border-line p-4">
      <Field label="What's misleading or missing?" htmlFor="note-claim">
        <Input id="note-claim" value={claim} maxLength={500} dir="auto" onChange={(e) => setClaim(e.target.value)} placeholder="e.g. The bus timetable didn't change" />
      </Field>
      <Field label="Context" hint="Neutral, in your own words. At least 20 characters." htmlFor="note-context">
        <Textarea id="note-context" value={context} maxLength={2000} dir="auto" onChange={(e) => setContext(e.target.value)} className="min-h-[96px]" />
      </Field>
      <Field label="Source" htmlFor="note-source">
        <Input id="note-source" type="url" value={source} onChange={(e) => setSource(e.target.value)} placeholder="https://" />
      </Field>
      <p className="text-caption text-muted">Notes are anonymous.</p>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onCancel}>Cancel</Button>
        <Button type="submit" disabled={busy || !ok}>Add note</Button>
      </div>
    </form>
  );
}

/** A post's reader notes (like X's Community Notes): read, rate, write. `onChanged` lets the
 *  post refresh its "Readers added context" block. */
export function PostNotes({ post, onChanged }) {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["notes", post.id], queryFn: () => getPostNotes(post.id), select: (d) => d.results ?? d });
  const [writing, setWriting] = useState(false);
  const notes = query.data || [];
  const changed = () => {
    queryClient.invalidateQueries({ queryKey: ["notes", post.id] });
    onChanged?.();
  };
  const mine = notes.some((n) => n.is_mine);
  return (
    <section aria-labelledby={`notes-${post.id}`}>
      <div className="flex items-center gap-2">
        <h2 id={`notes-${post.id}`} className="flex-1 text-title">Reader notes</h2>
        {!writing && !mine && (
          <Button variant="secondary" size="sm" onClick={() => setWriting(true)}><NotebookPen size={14} />Add context</Button>
        )}
      </div>
      <p className="mt-1 text-meta text-muted">A note is shown on the post once members in different situations rate it helpful.</p>
      {writing && <div className="mt-4"><NoteForm postId={post.id} onDone={() => { setWriting(false); changed(); }} onCancel={() => setWriting(false)} /></div>}
      {query.isPending ? (
        <p className="py-4 text-meta text-muted">Loading notes…</p>
      ) : notes.length ? (
        <ul className="divide-y divide-line">{notes.map((n) => <Note key={n.id} note={n} onChanged={changed} />)}</ul>
      ) : (
        !writing && <p className="py-4 text-meta text-muted">No notes yet.</p>
      )}
    </section>
  );
}
