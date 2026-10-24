import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, CircleHelp, Lightbulb, Megaphone, Send, Users } from "lucide-react";
import { useId, useState } from "react";
import { Link } from "react-router-dom";

import { Badge, Button, Field, RadioCards, Textarea, toast } from "@/components/ui";
import { Column, ColumnTitle, EmptyState, QueryBoundary } from "@/components/patterns";
import { useAuth } from "@/features/auth/AuthProvider";
import { timeAgo } from "@/lib/i18n";
import { getContributions, sendContribution } from "../api";
import { useCommunities } from "../hooks/useCommunities";

const KINDS = [
  { value: "question", label: "A question", hint: "Something you want explained or checked.", icon: CircleHelp, placeholder: "e.g. Why is the bus 3 timetable changing?" },
  { value: "tip", label: "A tip", hint: "Something happening that the newsroom should know.", icon: Megaphone, placeholder: "e.g. The Raksila pool is closed all week, there's a sign on the door." },
  { value: "topic_suggestion", label: "A story idea", hint: "A subject you'd like covered.", icon: Lightbulb, placeholder: "e.g. How daycare places are decided in Oulu." },
];
const kindOf = (k) => KINDS.find((x) => x.value === k) || KINDS[0];
const STATUS = {
  new: { label: "Sent", tone: "neutral" },
  in_review: { label: "An editor is reading it", tone: "neutral" },
  accepted: { label: "Becoming a story", tone: "newsroom" },
  answered: { label: "Answered", tone: "newsroom" },
  rejected: { label: "Not taken up", tone: "neutral" },
};
const MAX = 1000;

function History({ lang }) {
  const query = useQuery({ queryKey: ["contributions"], queryFn: getContributions, select: (d) => d.results ?? d });
  return (
    <section className="border-t border-line">
      <h2 className="px-4 pb-1 pt-6 text-caption font-semibold uppercase tracking-wide text-muted sm:px-6">What you've sent</h2>
      <QueryBoundary query={query} empty={<p className="px-4 pb-6 pt-2 text-meta text-muted sm:px-6">Nothing yet. What you send shows here, with where it stands.</p>}>
        {(list) => (
          <ul className="divide-y divide-line">
            {list.map((c) => {
              const { icon: Icon, label } = kindOf(c.kind);
              const status = STATUS[c.status] || STATUS.new;
              return (
                <li key={c.id} className="flex gap-3 px-4 py-4 sm:px-6">
                  <Icon size={16} className="mt-0.5 shrink-0 text-muted" aria-label={label} />
                  <div className="min-w-0 flex-1">
                    <p className="line-clamp-3 text-ui" dir="auto">{c.body}</p>
                    <p className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-caption text-muted">
                      <Badge tone={status.tone}>{status.label}</Badge>
                      <time dateTime={c.created_at}>{timeAgo(c.created_at, lang)}</time>
                      {c.occurrence_count > 1 && <span className="inline-flex items-center gap-1"><Users size={12} />{c.occurrence_count} readers asked this</span>}
                    </p>
                    {c.linked_snippet && (
                      <Link to={`/story/${c.linked_snippet}`} className="focus-ring mt-2 inline-flex items-center gap-1 rounded-control text-meta font-medium text-newsroom hover:underline">
                        Read the story<ArrowRight size={14} className="rtl:rotate-180" />
                      </Link>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </QueryBoundary>
    </section>
  );
}

/** Ask the newsroom: send a question, tip or story idea to the editors. Never published as written. */
export default function Ask() {
  const { me } = useAuth();
  const queryClient = useQueryClient();
  const groups = useCommunities();
  const [kind, setKind] = useState("question");
  const [body, setBody] = useState("");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const ids = { body: useId(), consent: useId() };

  const mine = (groups.data?.all || []).filter((g) => g.is_member);
  // Contributions are filed under the newsroom of the reader's community (the place one first).
  const community = mine.find((g) => g.kind === "geo") || mine[0];
  const current = kindOf(kind);

  const send = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const res = await sendContribution(community.id, kind, body.trim());
      setBody("");
      setConsent(false);
      queryClient.invalidateQueries({ queryKey: ["contributions"] });
      toast(res.occurrence_count > 1
        ? { title: "Sent. Others asked this too", description: `${res.occurrence_count} readers have asked it, which tells editors it matters.`, tone: "confirmed" }
        : { title: "Sent to the newsroom", description: "You'll see here when an editor picks it up.", tone: "confirmed" });
    } catch (err) {
      toast({ title: "It wasn't sent", description: Object.values(err.data || {}).flat()[0] || err.message, tone: "danger" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Column header={<ColumnTitle title="Ask the newsroom" subtitle="Editors read everything. Nothing is published as you wrote it." />}>
      {groups.data && !community ? (
        <EmptyState
          icon={Users}
          title="Join a community first"
          action={<Button asChild><Link to="/communities/browse">Find communities</Link></Button>}
        >
          What you send goes to the newsroom that covers your community.
        </EmptyState>
      ) : (
        <form onSubmit={send} className="flex flex-col gap-6 px-4 py-6 sm:px-6">
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-2 text-meta font-medium">What is it?</legend>
            <RadioCards
              value={kind}
              onValueChange={setKind}
              options={KINDS}
              columns="sm:grid-cols-3"
              renderOption={({ icon: Icon, label, hint }) => (
                <span className="flex items-start gap-3 sm:flex-col sm:gap-2">
                  <Icon size={18} className="mt-0.5 shrink-0 text-muted sm:mt-0" />
                  <span className="flex flex-col"><span className="text-ui font-medium">{label}</span><span className="text-caption text-muted">{hint}</span></span>
                </span>
              )}
            />
          </fieldset>

          <Field label="Your message" htmlFor={ids.body} hint={`Write in any language. ${body.length}/${MAX}`}>
            <Textarea id={ids.body} value={body} onChange={(e) => setBody(e.target.value)} maxLength={MAX} dir="auto" placeholder={current.placeholder} className="min-h-[140px]" />
          </Field>

          <label htmlFor={ids.consent} className="flex cursor-pointer items-start gap-3 text-meta">
            <input id={ids.consent} type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="focus-ring mt-0.5 h-4 w-4 shrink-0 accent-ink" />
            <span>
              The newsroom may use what I wrote when reporting. My name isn't published.
              <span className="block text-caption text-muted">Please don't name private people without their permission.</span>
            </span>
          </label>

          <div className="flex justify-end">
            <Button type="submit" size="lg" disabled={busy || !body.trim() || !consent || !community}>
              <Send size={15} className="rtl:rotate-180" />Send to the newsroom
            </Button>
          </div>
        </form>
      )}
      <History lang={me?.preferred_language} />
    </Column>
  );
}
