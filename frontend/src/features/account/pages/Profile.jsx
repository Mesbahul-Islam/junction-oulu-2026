import { useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Bookmark, LogOut, Trophy } from "lucide-react";
import { useEffect, useId, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { Avatar, Button, Input, Switch, toast } from "@/components/ui";
import { Column, ColumnTitle } from "@/components/patterns";
import { useAuth } from "@/features/auth/AuthProvider";
import { useCommunities } from "@/features/communities/hooks/useCommunities";
import { useFantasyMode } from "@/features/fantasy/lib/fantasyMode";
import { preloadFantasy } from "@/features/fantasy/lib/fantasyPreload";
import { useSaved } from "@/features/feed/hooks/useFeed";
import { LANGUAGES, SITUATIONS, timeAgo, topicIcon, topicLabel } from "@/lib/i18n";
import { updateMe } from "../api";

const selectCls =
  "focus-ring h-9 w-full rounded-control border border-line bg-surface px-2 text-ui text-ink sm:w-60 md:text-[14px] [@media(pointer:coarse)]:h-11";

function Section({ title, action, children }) {
  return (
    <section className="border-b border-line px-4 py-6 sm:px-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-caption font-semibold uppercase tracking-wide text-muted">{title}</h2>
        {action}
      </div>
      <div className="mt-2 divide-y divide-line">{children}</div>
    </section>
  );
}

/** Label and help on the start, the control on the end; stacked on phones. */
function Row({ label, hint, htmlFor, children }) {
  return (
    <div className="flex flex-col gap-2 py-3.5 sm:flex-row sm:items-center sm:gap-6">
      <div className="min-w-0 flex-1">
        <label htmlFor={htmlFor} className="text-ui font-medium text-ink">{label}</label>
        {hint && <p className="text-meta text-muted">{hint}</p>}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

/** A text setting that saves on Save (or Enter) and says why if the server refuses it. */
function TextSetting({ label, hint, value, field, transform = (v) => v, onSaved }) {
  const id = useId();
  const [draft, setDraft] = useState(value || "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => setDraft(value || ""), [value]);
  const dirty = draft.trim() !== (value || "");
  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await updateMe({ [field]: draft.trim() });
      await onSaved();
      toast({ title: `${label} saved`, tone: "confirmed" });
    } catch (err) {
      setError(err.data?.[field]?.[0] || err.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={save}>
      <Row label={label} hint={error ? undefined : hint} htmlFor={id}>
        <div className="flex gap-2">
          <Input id={id} value={draft} maxLength={30} onChange={(e) => setDraft(transform(e.target.value))} aria-invalid={!!error} className="sm:w-60" />
          {dirty && <Button type="submit" size="md" disabled={busy || !draft.trim()}>Save</Button>}
        </div>
      </Row>
      {error && <p role="alert" className="-mt-2 pb-3 text-meta text-danger sm:text-end">{error}</p>}
    </form>
  );
}

export default function Profile() {
  const { me, logout, refresh } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const saved = useSaved();
  const groups = useCommunities();
  const [fantasyMode, setFantasyMode] = useFantasyMode();
  // Fantasy mode on: fetch the game's data and warm player photos now, before the reader taps in.
  useEffect(() => { if (fantasyMode) preloadFantasy(); }, [fantasyMode]);

  // Language and situation change what every story says, so refetch everything after.
  const change = async (data, title) => {
    try {
      await updateMe(data);
      await refresh();
      queryClient.invalidateQueries();
      toast({ title, tone: "confirmed" });
    } catch (e) {
      toast({ title: "That wasn't saved", description: Object.values(e.data || {}).flat()[0] || e.message, tone: "danger" });
    }
  };

  const ids = { lang: useId(), situation: useId(), arrival: useId(), fantasy: useId() };
  const mine = (groups.data?.all || []).filter((g) => g.is_member);
  const savedList = saved.data || [];
  const name = me.display_name || `@${me.username}`;

  return (
    <Column header={<ColumnTitle title="You" />}>
      <div className="flex items-center gap-4 border-b border-line px-4 py-6 sm:px-6">
        <Avatar name={me.display_name || me.username} size="lg" />
        <div className="min-w-0">
          <p className="truncate text-headline">{name}</p>
          <p className="truncate text-meta text-muted">@{me.username} · {me.email}</p>
        </div>
      </div>

      <Section title="Reading">
        <Row label="Language" hint="Stories show in it once a person approves the translation." htmlFor={ids.lang}>
          <select id={ids.lang} className={selectCls} value={me.preferred_language || "en"} onChange={(e) => change({ preferred_language: e.target.value }, "Language changed")}>
            {LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.name === l.english ? l.name : `${l.name} · ${l.english}`}</option>)}
          </select>
        </Row>
        <Row label="Your situation" hint={`Shapes "What this means for you" on every story.`} htmlFor={ids.situation}>
          <select id={ids.situation} className={selectCls} value={me.reader_situation || ""} onChange={(e) => change({ reader_situation: e.target.value }, "Situation changed")}>
            {SITUATIONS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </Row>
        <Row label="Arrived in Finland" hint="For your first-weeks guide on Today. Leave empty if it doesn't apply." htmlFor={ids.arrival}>
          <Input id={ids.arrival} type="date" className="sm:w-60" value={me.arrival_date || ""} max={new Date().toISOString().slice(0, 10)}
            onChange={(e) => change({ arrival_date: e.target.value || null }, "Arrival date saved")} />
        </Row>
        <div className="flex flex-col gap-3 py-3.5">
          <div className="flex items-center justify-between gap-3">
            <p className="text-ui font-medium">Topics you follow</p>
            <Button asChild variant="ghost" size="sm"><Link to="/onboarding">Edit</Link></Button>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {(me.profile?.interests || []).map((t) => {
              const Icon = topicIcon(t);
              return <span key={t} className="inline-flex items-center gap-1.5 rounded-pill border border-line px-3 py-1 text-meta"><Icon size={14} className="text-muted" />{topicLabel(t)}</span>;
            })}
          </div>
        </div>
      </Section>

      <Section title="Saved" action={savedList.length > 3 && <Button asChild variant="ghost" size="sm"><Link to="/saved">See all {savedList.length}</Link></Button>}>
        {savedList.length ? savedList.slice(0, 3).map((s) => (
          <Link key={s.id} to={`/story/${s.id}`} state={s} className="focus-ring group flex items-center gap-3 rounded-control py-3">
            <Bookmark size={15} className="shrink-0 text-muted" fill="currentColor" />
            <span className="min-w-0 flex-1 truncate text-ui group-hover:underline" dir="auto">{s.headline}</span>
            <span className="shrink-0 text-caption text-muted">{timeAgo(s.published_at, me.preferred_language)}</span>
          </Link>
        )) : (
          <p className="py-3 text-meta text-muted">Nothing saved yet. Tap the bookmark on a story to keep it here.</p>
        )}
      </Section>

      <Section title="Communities" action={<Button asChild variant="ghost" size="sm"><Link to="/communities/browse">Manage</Link></Button>}>
        {mine.length ? (
          <p className="py-3 text-ui">{mine.map((g) => g.name).join(" · ")}</p>
        ) : (
          <p className="py-3 text-meta text-muted">You haven't joined any yet. Communities let you ask neighbours and vote on Next stories.</p>
        )}
      </Section>

      <Section title="Account">
        <TextSetting label="Display name" hint="Shown on your profile." field="display_name" value={me.display_name} onSaved={refresh} />
        <TextSetting label="Username" hint="Shown on your posts and replies." field="username" value={me.username} transform={(v) => v.replace(/\s/g, "")} onSaved={refresh} />
        <Row label="Email" hint="Used to log in. It isn't shown to anyone.">
          <p className="text-ui text-muted">{me.email}</p>
        </Row>
      </Section>

      <Section title="Extras">
        <Row label="Lämäri fantasy hockey" hint="Pick a Liiga team and compete with friends. Saved on this device." htmlFor={ids.fantasy}>
          <Switch id={ids.fantasy} checked={fantasyMode} onCheckedChange={setFantasyMode} />
        </Row>
        {fantasyMode && (
          <Link to="/fantasy" className="focus-ring group flex items-center gap-3 rounded-control py-3.5">
            <Trophy size={16} className="text-muted" />
            <span className="flex-1 text-ui font-medium group-hover:underline">Open Lämäri</span>
            <ArrowRight size={16} className="text-muted rtl:rotate-180" />
          </Link>
        )}
      </Section>

      <div className="px-4 py-6 sm:px-6">
        <Button variant="secondary" onClick={() => { logout(); navigate("/welcome"); }}>
          <LogOut size={15} className="rtl:rotate-180" />Log out
        </Button>
      </div>
    </Column>
  );
}
