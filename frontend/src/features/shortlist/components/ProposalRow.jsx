import { ExternalLink, Languages, ThumbsUp } from "lucide-react";
import { useState } from "react";

import { Button, Meter } from "@/components/ui";
import { languageName } from "@/lib/i18n";
import { useVote } from "../hooks/useShortlist";

const host = (u) => { try { return new URL(u).hostname.replace(/^www\./, ""); } catch { return u; } };
const votesLabel = (n) => (n === 1 ? "1 vote" : `${n} votes`);

/** A story the newsroom hasn't written yet, votable in place. `rank` shows its place on the
 *  list; `maxVotes` scales the meter against the most-wanted proposal. */
export function ProposalRow({ item, rank, maxVotes = 0, canVote = true, detail = true }) {
  const vote = useVote();
  const [original, setOriginal] = useState(false);
  const title = original ? item.original_title : item.title;
  return (
    <div className="flex items-start gap-3 sm:gap-4">
      {rank != null && (
        <span className="mt-0.5 w-6 shrink-0 text-end text-title tabular-nums text-muted">{rank}</span>
      )}
      <div className="min-w-0 flex-1" dir="auto">
        <h3 className="text-title text-balance" lang={original ? "fi" : item.language}>{title}</h3>
        <p className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-caption text-muted">
          <a href={item.url} target="_blank" rel="noreferrer" className="focus-ring inline-flex items-center gap-1 rounded-control hover:text-ink">
            {host(item.url)}<ExternalLink size={11} />
          </a>
          {item.translated && (
            <button type="button" onClick={() => setOriginal(!original)} className="focus-ring inline-flex items-center gap-1 rounded-control hover:text-ink">
              <Languages size={12} />{original ? `Show in ${languageName(item.language)}` : "Title machine-translated · show original"}
            </button>
          )}
          {detail && item.reasons?.map((r) => <span key={r}>Shortlisted for {r}</span>)}
        </p>
        {maxVotes > 0 && (
          <Meter className="mt-3" label="Readers who want it" value={item.votes} max={maxVotes} display={votesLabel(item.votes)} />
        )}
      </div>
      {item.image_url && detail && (
        <img src={item.image_url} alt="" loading="lazy" referrerPolicy="no-referrer" onError={(e) => e.currentTarget.remove()} className="hidden h-16 w-16 shrink-0 rounded-control bg-sunk object-cover sm:block" />
      )}
      <Button
        variant={item.voted ? "primary" : "secondary"}
        size="sm"
        onClick={() => vote(item)}
        disabled={!canVote}
        aria-pressed={item.voted}
        aria-label={`${item.voted ? "Take back your vote" : "Vote"} (${votesLabel(item.votes)})`}
        className="tabular-nums"
      >
        <ThumbsUp size={14} fill={item.voted ? "currentColor" : "none"} />{item.voted ? "Voted" : "Vote"}
        <span className={item.voted ? "text-on-ink/70" : "text-muted"}>{item.votes}</span>
      </Button>
    </div>
  );
}
