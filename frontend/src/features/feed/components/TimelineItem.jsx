import { Bookmark, MessageCircle, MoreHorizontal, Share2 } from "lucide-react";
import { Link } from "react-router-dom";

import { Avatar } from "@/components/ui";
import { LangStatus, langStatusOf } from "@/components/patterns";
import { languageName, timeAgo } from "@/lib/i18n";
import { cn } from "@/lib/utils";

function titleCase(slug) {
  return slug.replace(/[-_]/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

export function TimelineItem({ card, lang, onOpen, className }) {
  const Wrapper = onOpen ? "button" : Link;
  const wrapperProps = onOpen ? { type: "button", onClick: onOpen } : { to: `/story/${card.id}`, state: card };
  const status = langStatusOf(card);
  const isCommunity = card.community && !card.author?.toLowerCase().includes("newsroom");

  return (
    <article
      className={cn(
        "group relative flex gap-3 border-b border-line px-4 py-4 transition-colors hover:bg-ink/[0.01] sm:px-6",
        className,
      )}
    >
      <div className="shrink-0">
        {isCommunity ? (
          <Avatar name={card.community} community size="md" />
        ) : (
          <Avatar name={card.author || "Newsroom"} size="md" />
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-2">
          <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-ui">
            <span className="truncate font-medium text-ink">
              {isCommunity ? titleCase(card.community) : card.author || "Oulu News"}
            </span>
            <span className="text-muted">·</span>
            {card.published_at && (
              <time dateTime={card.published_at} className="shrink-0 text-muted">
                {timeAgo(card.published_at, lang)}
              </time>
            )}
            {!card.in_your_language && card.requested_language && (
              <span className="rounded-pill bg-sunk px-2 py-0.5 text-caption text-muted">
                {languageName(card.requested_language)}
              </span>
            )}
          </div>
          <button
            type="button"
            aria-label="More"
            className="focus-ring -mr-1.5 rounded-full p-1.5 text-muted opacity-0 transition-opacity hover:bg-ink/5 hover:text-ink group-hover:opacity-100"
          >
            <MoreHorizontal size={18} />
          </button>
        </div>

        <Wrapper {...wrapperProps} dir="auto" className="mt-1 block focus-ring rounded-control text-start">
          <h3 className="text-title text-balance">{card.headline}</h3>
          {card.summary && <p className="mt-1 line-clamp-3 text-ui text-muted">{card.summary}</p>}
        </Wrapper>

        {status && (
          <div className="mt-2">
            <LangStatus {...status} />
          </div>
        )}

        {card.image_url && (
          <Wrapper {...wrapperProps} className="mt-3 block overflow-hidden rounded-card border border-line">
            <img
              src={card.image_url}
              alt=""
              loading="lazy"
              referrerPolicy="no-referrer"
              onError={(e) => e.currentTarget.parentElement.remove()}
              className="aspect-[16/9] w-full object-cover"
            />
          </Wrapper>
        )}

        <div className="mt-3 flex items-center gap-1 text-muted sm:gap-2">
          <button type="button" className="focus-ring flex items-center gap-1.5 rounded-full px-2 py-1.5 text-meta hover:bg-newsroom/5 hover:text-newsroom">
            <MessageCircle size={18} />
            {card.metrics?.comments ? <span>{card.metrics.comments}</span> : null}
          </button>
          <button type="button" className="focus-ring flex items-center gap-1.5 rounded-full px-2 py-1.5 text-meta hover:bg-confirmed/5 hover:text-confirmed">
            <Share2 size={18} />
          </button>
          <button type="button" className="focus-ring flex items-center gap-1.5 rounded-full px-2 py-1.5 text-meta hover:bg-community/5 hover:text-community">
            <Bookmark size={18} />
          </button>
        </div>
      </div>
    </article>
  );
}
