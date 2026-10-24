import { Bookmark, ChevronRight, CircleAlert, MessageCircle, Share2, ShieldCheck, Sparkles, Users } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Badge, Dialog, DialogContent, DialogTrigger, Meter, toast } from "@/components/ui";
import { LangStatus, langStatusOf } from "@/components/patterns";
import { languageName, SITUATIONS, timeAgo } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { interact } from "../api";

/** One line saying why this story needs the reader now, from the Jev re-rank. Null when the
 *  heuristic ranked it (no per-reader answers) or nothing stands out. */
export function signalOf(ranking) {
  const j = ranking?.jev;
  if (!j) return null;
  // urgency is 0–3: not time-sensitive / this month / this week / today or tomorrow (feed/jev.py).
  if (j.needs_action >= 0.5 && j.urgency >= 2.5) return "Act today or tomorrow";
  if (j.needs_action >= 0.5 && j.urgency >= 1.5) return "Act this week";
  if (j.affects_reader >= 0.6) return "Affects you";
  return null;
}

export const situationShort = (s) => SITUATIONS.find((x) => x.value === s)?.short;

/** Save + share for one story, with the ranking signals the backend learns from. */
export function useStoryActions(card) {
  const [saved, setSaved] = useState(!!card.bookmarked);
  const toggleSave = async () => {
    setSaved(!saved);
    try {
      const res = await interact(card.id, saved ? "unbookmark" : "bookmark");
      setSaved(res.active);
    } catch (e) {
      setSaved(saved);
      toast({ title: "Couldn't save the story", description: e.message, tone: "danger" });
    }
  };
  const share = async () => {
    const url = `${window.location.origin}/story/${card.id}`;
    if (navigator.share) await navigator.share({ title: card.headline, url }).catch(() => {});
    else {
      await navigator.clipboard?.writeText(url);
      toast({ title: "Link copied" });
    }
    interact(card.id, "share").catch(() => {});
  };
  return { saved, toggleSave, share };
}

/** "Why am I seeing this?": the four per-reader answers Jev gave, as meters. */
export function WhyThis({ ranking }) {
  const j = ranking?.jev;
  if (!j) return null;
  return (
    <div className="flex flex-col gap-4">
      <Meter label="Affects your daily life" value={j.affects_reader} />
      <Meter label="Matches your interests" value={j.matches_interests} />
      <Meter label="Something to do" value={j.needs_action} />
      <Meter label="Time-sensitive" value={j.urgency} max={3} display={["Not urgent", "This month", "This week", "Today"][Math.round(j.urgency)]} />
    </div>
  );
}

const iconBtn = "focus-ring inline-flex h-9 min-w-9 items-center justify-center gap-1.5 rounded-control px-2 text-meta text-muted transition-colors hover:bg-ink/5 hover:text-ink [@media(pointer:coarse)]:h-11 [@media(pointer:coarse)]:min-w-11";

/** A newsroom story in the Today timeline. `onOpen(card)` opens it in the side peek; plain
 *  clicks fall back to the story page (and cmd-click still opens a new tab). */
export function StoryRow({ card, lang, situation, onOpen, active }) {
  const { saved, toggleSave, share } = useStoryActions(card);
  const signal = signalOf(card.ranking);
  const status = langStatusOf(card);
  const facts = card.key_facts || [];
  const open = (e) => {
    if (!onOpen || e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    onOpen(card);
  };
  const href = `/story/${card.id}`;

  return (
    <article className={cn("relative border-b border-line px-4 py-5 transition-colors sm:px-6", active && "bg-sunk/60")} dir="auto">
      <header className="flex items-center gap-2 text-meta">
        <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-newsroom-weak text-newsroom">
          <ShieldCheck size={13} />
        </span>
        <span className="font-medium text-ink">Oulu News</span>
        {card.community_name && <span className="truncate text-muted">{card.community_name}</span>}
        <span className="text-muted" aria-hidden="true">·</span>
        <time dateTime={card.published_at} className="shrink-0 text-muted">{timeAgo(card.published_at, lang)}</time>
      </header>

      <Link to={href} state={card} onClick={open} className="group mt-3 flex gap-4 rounded-control focus-ring">
        <div className="flex min-w-0 flex-1 flex-col gap-1.5">
          {signal && (
            <span className="flex items-center gap-1.5 text-caption font-semibold uppercase tracking-wide text-ink">
              <span className="h-1.5 w-1.5 rounded-full bg-ink" aria-hidden="true" />{signal}
            </span>
          )}
          <h2 className="text-title text-balance decoration-line decoration-2 underline-offset-4 group-hover:underline">{card.headline}</h2>
          {card.summary && <p className="line-clamp-2 text-ui text-muted">{card.summary}</p>}
        </div>
        {card.image_url && (
          <img
            src={card.image_url}
            alt=""
            loading="lazy"
            referrerPolicy="no-referrer"
            onError={(e) => e.currentTarget.remove()}
            className="h-[72px] w-[72px] shrink-0 rounded-control bg-sunk object-cover sm:h-[96px] sm:w-[96px]"
          />
        )}
      </Link>

      {card.for_you && (
        <div className="mt-3 border-s-2 border-newsroom ps-3">
          <p className="text-caption font-semibold text-newsroom">
            For you as {situationShort(card.situation) || "a reader"}
            {card.for_you_language && card.for_you_language !== card.language && ` · in ${languageName(card.for_you_language)}`}
          </p>
          <p className="mt-0.5 line-clamp-3 text-meta text-ink/90" lang={card.for_you_language || undefined}>{card.for_you}</p>
        </div>
      )}

      {facts.length > 0 && (
        <details
          className="group/facts mt-3"
          onToggle={(e) => e.currentTarget.open && interact(card.id, "expand").catch(() => {})}
        >
          <summary className="focus-ring inline-flex cursor-pointer list-none items-center gap-1 rounded-control text-meta font-medium text-muted hover:text-ink [&::-webkit-details-marker]:hidden">
            <ChevronRight size={15} className="transition-transform group-open/facts:rotate-90 rtl:rotate-180 rtl:group-open/facts:rotate-90" />
            {facts.length} key {facts.length === 1 ? "fact" : "facts"}
          </summary>
          <ul className="mt-2 flex flex-col gap-1.5 ps-5">
            {facts.map((f) => <li key={f} className="list-disc text-meta text-ink/90 marker:text-muted">{f}</li>)}
          </ul>
        </details>
      )}

      <footer className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="inline-flex items-center gap-1 text-caption text-muted">
          <ShieldCheck size={13} className="text-newsroom" />
          Checked by {card.ai_disclosure?.reviewer || "an editor"}
          {card.ai_disclosure?.ai_generated && " · AI-assisted"}
        </span>
        {status && status.state !== "original" && <LangStatus {...status} />}
        {card.correction_note && <Badge tone="danger"><CircleAlert size={12} />Corrected</Badge>}
        {card.community_notes?.length > 0 && <Badge tone="confirmed"><Users size={12} />Reader note</Badge>}

        <div className="-me-2 ms-auto flex items-center">
          {card.ranking?.jev && (
            <Dialog>
              <DialogTrigger className={iconBtn} aria-label="Why am I seeing this?"><Sparkles size={16} /></DialogTrigger>
              <DialogContent title="Why you're seeing this" description="How this story fits you, as judged for your situation, area and interests. Nothing about you that identifies you is used.">
                <WhyThis ranking={card.ranking} />
              </DialogContent>
            </Dialog>
          )}
          <Link to={href} state={card} onClick={open} className={iconBtn} aria-label="Comments">
            <MessageCircle size={16} />{card.metrics?.comments > 0 && card.metrics.comments}
          </Link>
          <button type="button" className={iconBtn} onClick={share} aria-label="Share"><Share2 size={16} /></button>
          <button type="button" className={cn(iconBtn, saved && "text-ink")} onClick={toggleSave} aria-pressed={saved} aria-label={saved ? "Remove from saved" : "Save"}>
            <Bookmark size={16} fill={saved ? "currentColor" : "none"} />
          </button>
        </div>
      </footer>
    </article>
  );
}
