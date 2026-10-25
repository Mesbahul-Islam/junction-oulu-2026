import { useQuery } from "@tanstack/react-query";
import {
  Bookmark, ChevronRight, CircleAlert, ExternalLink, Flag, Languages, Pause, Share2, Sparkles, Users, Volume2,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button, Dialog, DialogClose, DialogContent, DialogTrigger, Field, RadioCards, Textarea, toast } from "@/components/ui";
import { LangStatus, langStatusOf, NeedTag, Provenance, QueryBoundary, TrustBlock } from "@/components/patterns";
import { languageName, timeAgo, topicLabel } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { getStory, interact, reportStory } from "../api";
import { useListen } from "../hooks/useListen";
import { situationShort, useStoryActions, WhyThis } from "./StoryRow";

const ROLE = {
  wire: "wire", news_editor: "news editor", reporter: "reporter", explainer: "explainer", translator: "translator",
  fact_checker: "fact-checker", standards: "standards", copy_desk: "copy desk", community_vote: "community vote",
};
const REASONS = [
  { value: "wrong", label: "Something is wrong" },
  { value: "outdated", label: "It's out of date" },
  { value: "translation", label: "The translation is wrong" },
  { value: "other", label: "Something else" },
];
const host = (u) => { try { return new URL(u).hostname.replace(/^www\./, ""); } catch { return u; } };

/** Native disclosure in Kajo's quiet style; `onOpen` fires once per opening. */
function More({ title, icon: Icon, onOpen, children }) {
  return (
    <details className="group/more border-t border-line py-3" onToggle={(e) => e.currentTarget.open && onOpen?.()}>
      <summary className="focus-ring flex cursor-pointer list-none items-center gap-2 rounded-control text-ui font-medium text-ink [&::-webkit-details-marker]:hidden">
        {Icon && <Icon size={16} className="text-muted" />}
        <span className="flex-1">{title}</span>
        <ChevronRight size={16} className="text-muted transition-transform group-open/more:rotate-90" />
      </summary>
      <div className="pt-3">{children}</div>
    </details>
  );
}

function ReportDialog({ id, onReported }) {
  const [reason, setReason] = useState("wrong");
  const [body, setBody] = useState("");
  const [sending, setSending] = useState(false);
  const send = async () => {
    setSending(true);
    try {
      await reportStory(id, reason, body);
      toast({ title: "Thanks, an editor will check it", description: "The story is paused until then.", tone: "confirmed" });
      onReported?.();
    } catch (e) {
      toast({ title: "Couldn't send the report", description: e.message, tone: "danger" });
    } finally {
      setSending(false);
    }
  };
  return (
    <Dialog>
      <Button asChild variant="ghost" size="sm" className="-ms-2.5 text-muted">
        <DialogTrigger><Flag size={15} />Report a problem</DialogTrigger>
      </Button>
      <DialogContent title="What's the problem?" description="An editor reads every report. The story is paused while they check it.">
        <RadioCards value={reason} onValueChange={setReason} options={REASONS} renderOption={(o) => <span className="text-ui">{o.label}</span>} />
        <Field label="What should change? (optional)" htmlFor="report-body">
          <Textarea id="report-body" value={body} onChange={(e) => setBody(e.target.value)} className="min-h-[88px]" />
        </Field>
        <div className="flex justify-end gap-2">
          <DialogClose asChild><Button variant="ghost">Cancel</Button></DialogClose>
          <Button onClick={send} disabled={sending}>{sending ? "Sending…" : "Send report"}</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function Body({ card, ranking, lang, size, onReported }) {
  const { saved, toggleSave, share } = useStoryActions(card);
  const listenText = [card.headline, card.summary, ...(card.key_facts || []), card.for_you || ""].join(". ");
  const listen = useListen(listenText, card.language || "en", card.id);
  const status = langStatusOf(card);
  const ai = card.ai_disclosure || {};
  const endRef = useRef(null);
  const expand = () => interact(card.id, "expand").catch(() => {});

  // Reaching the end counts as reading it through (a ranking signal).
  useEffect(() => {
    if (!endRef.current) return;
    const io = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) { interact(card.id, "read_through").catch(() => {}); io.disconnect(); }
    }, { threshold: 1 });
    io.observe(endRef.current);
    return () => io.disconnect();
  }, [card.id]);

  return (
    <article dir="auto" data-story={card.id} className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-meta text-muted">
        {card.community_name && <span className="font-medium text-ink">{card.community_name}</span>}
        <time dateTime={card.published_at}>{timeAgo(card.published_at, lang)}</time>
        {status && <LangStatus {...status} />}
        {card.reader_needs?.[0] && <NeedTag need={card.reader_needs[0]} />}
      </div>

      <div className="flex flex-col gap-3">
        <h1 data-story-part="headline" className={cn("text-balance", size === "page" ? "text-display" : "text-headline")}>{card.headline}</h1>
        {card.summary && <p className="text-lead text-ink/85">{card.summary}</p>}
      </div>

      <div className="-ms-2.5 flex flex-wrap items-center gap-1">
        {listen.supported && (
          <Button variant="ghost" size="sm" onClick={listen.toggle} aria-pressed={listen.playing} aria-busy={listen.loading}>
            {listen.playing ? <Pause size={15} /> : <Volume2 size={15} />}
            {listen.loading ? "Preparing…" : listen.playing ? "Stop" : `Listen · ${Math.max(1, Math.round(listen.duration / 60))} min`}
          </Button>
        )}
        <Button variant="ghost" size="sm" onClick={toggleSave} aria-pressed={saved}>
          <Bookmark size={15} fill={saved ? "currentColor" : "none"} />{saved ? "Saved" : "Save"}
        </Button>
        <Button variant="ghost" size="sm" onClick={share}><Share2 size={15} />Share</Button>
      </div>

      {card.image_url && (
        <img src={card.image_url} alt="" referrerPolicy="no-referrer" onError={(e) => e.currentTarget.remove()} data-story-part="image" className="aspect-[16/9] w-full rounded-card bg-sunk object-cover" />
      )}

      {status?.state === "fallback" && (
        <TrustBlock tone="neutral" icon={Languages} title={`Not yet in ${languageName(card.requested_language)}`}>
          <p>You're reading the {languageName(card.language)} text until a person approves the translation.</p>
        </TrustBlock>
      )}
      {card.correction_note && (
        <TrustBlock tone="danger" icon={CircleAlert} title="Corrected"><p>{card.correction_note}</p></TrustBlock>
      )}
      {card.for_you && (
        <TrustBlock tone="newsroom" title={`What this means for you as ${situationShort(card.situation) || "a reader"}`}>
          <p lang={card.for_you_language || undefined}>{card.for_you}</p>
          {card.for_you_language && card.for_you_language !== card.language && (
            <p className="text-meta text-muted">Written in {languageName(card.for_you_language)}; not translated yet.</p>
          )}
        </TrustBlock>
      )}

      {card.key_facts?.length > 0 && (
        <section>
          <h2 className="text-title">Key facts</h2>
          {/* New stories have one paragraph (from the full article); older ones a list. */}
          {card.key_facts.length === 1 ? (
            <p className="mt-2 text-body">{card.key_facts[0]}</p>
          ) : (
            <ul className="mt-2 flex flex-col gap-2 ps-5">
              {card.key_facts.map((f) => <li key={f} className="list-disc text-body marker:text-muted">{f}</li>)}
            </ul>
          )}
        </section>
      )}

      {card.community_notes?.map((n) => (
        <TrustBlock key={n.id} tone="confirmed" icon={Users} title="Readers added context">
          <p className="font-medium">{n.claim_summary}</p>
          <p>{n.context}</p>
          {n.citation_urls?.length > 0 && (
            <p className="flex flex-wrap gap-x-3 text-meta">
              {n.citation_urls.map((u) => <a key={u} href={u} target="_blank" rel="noreferrer" className="underline decoration-line underline-offset-2 hover:decoration-ink">{host(u)}</a>)}
            </p>
          )}
        </TrustBlock>
      ))}

      {card.background && (
        <TrustBlock tone="neutral" title="Background"><p>{card.background}</p></TrustBlock>
      )}

      <div>
        {card.original && (
          <More title={`Read the ${languageName(card.original.language)} original`} icon={Languages} onOpen={expand}>
            <div lang={card.original.language} className="flex flex-col gap-2">
              <p className="text-title">{card.original.headline}</p>
              <p className="text-ui text-ink/85">{card.original.summary}</p>
              {card.original.key_facts?.length > 0 && (
                card.original.key_facts.length === 1
                  ? <p className="text-ui">{card.original.key_facts[0]}</p>
                  : <ul className="flex flex-col gap-1 ps-5">{card.original.key_facts.map((f) => <li key={f} className="list-disc text-ui">{f}</li>)}</ul>
              )}
            </div>
          </More>
        )}
        {ranking?.jev && (
          <More title="Why you're seeing this" icon={Sparkles}><WhyThis ranking={ranking} /></More>
        )}
        <More title={`Sources (${card.source_urls?.length || 0})`} icon={ExternalLink}>
          <ul className="flex flex-col gap-2">
            {(card.source_urls || []).map((u) => (
              <li key={u}>
                <a href={u} target="_blank" rel="noreferrer" className="focus-ring inline-flex items-center gap-1.5 rounded-control text-ui underline decoration-line underline-offset-2 hover:decoration-ink">
                  {host(u)}<ExternalLink size={13} className="text-muted" />
                </a>
              </li>
            ))}
          </ul>
        </More>
      </div>

      <section className="flex flex-col gap-3 border-t border-line pt-5">
        <Provenance kind="newsroom" reviewer={ai.reviewer} date={ai.verified_at} machineTranslated={ai.machine_translated} />
        {ai.roles?.length > 0 && (
          <p className="text-caption text-muted">
            Drafted with AI desks: {ai.roles.map((r) => ROLE[r] || r).join(", ")}. A person approved it before it was published.
          </p>
        )}
        {card.tags?.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {card.tags.map((t) => <span key={t} className="rounded-pill bg-sunk px-2.5 py-0.5 text-caption text-muted">{topicLabel(t)}</span>)}
          </div>
        )}
        <div><ReportDialog id={card.id} onReported={onReported} /></div>
      </section>
      <div ref={endRef} className="h-px" />
    </article>
  );
}

/** A story for reading: in the side peek (`size="peek"`) or on its own page (`size="page"`).
 *  `card` (from the feed) shows instantly while the fresh copy loads. Ranking only comes with
 *  feed cards, so it is passed separately. */
export function StoryView({ id, card, ranking, lang, size = "peek", onReported }) {
  const query = useQuery({ queryKey: ["story", String(id)], queryFn: () => getStory(id), placeholderData: card });
  useEffect(() => { interact(id, "view").catch(() => {}); }, [id]);
  return (
    <QueryBoundary query={query} isEmpty={() => false}>
      {(data) => <Body key={data.id} card={data} ranking={ranking ?? data.ranking} lang={lang} size={size} onReported={onReported} />}
    </QueryBoundary>
  );
}
