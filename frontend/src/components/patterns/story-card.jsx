import { Users } from "lucide-react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui";
import { timeAgo } from "@/lib/i18n";
import { cn } from "@/lib/utils";

import { LangStatus, langStatusOf, NeedTag } from "./trust";

const titleCase = (slug) => slug.replace(/[-_]/g, " ").replace(/^\w/, (c) => c.toUpperCase());

function Meta({ card, lang }) {
  const status = langStatusOf(card);
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
      {status && <LangStatus {...status} />}
      {card.reader_needs?.[0] && <NeedTag need={card.reader_needs[0]} />}
      {card.published_at && <time dateTime={card.published_at} className="text-caption text-muted">{timeAgo(card.published_at, lang)}</time>}
    </div>
  );
}

/** A story in a list. `variant="lead"` for the top story (picture first, bigger headline).
 *  Pass `onOpen` to handle the tap yourself; otherwise it links to the story page. */
export function StoryCard({ card, variant = "row", lang, onOpen, className }) {
  const Wrapper = onOpen ? "button" : Link;
  const wrapperProps = onOpen ? { type: "button", onClick: onOpen } : { to: `/story/${card.id}`, state: card };
  const img = card.image_url && (
    <img
      src={card.image_url}
      alt=""
      loading="lazy"
      referrerPolicy="no-referrer"
      onError={(e) => e.currentTarget.remove()}
      className={cn("bg-sunk object-cover", variant === "lead" ? "aspect-[16/9] w-full rounded-card" : "h-[88px] w-[88px] shrink-0 rounded-control")}
    />
  );
  const fromCommunity = card.community && (
    <Badge tone="community"><Users size={12} />Asked for by {titleCase(card.community)}</Badge>
  );

  if (variant === "lead")
    return (
      <Wrapper {...wrapperProps} dir="auto" className={cn("focus-ring group flex w-full flex-col gap-4 rounded-card py-5 text-start", className)}>
        {img}
        <div className="flex flex-col gap-2">
          {fromCommunity && <div>{fromCommunity}</div>}
          <h2 className="text-headline sm:text-display text-balance decoration-line decoration-2 underline-offset-4 group-hover:underline">{card.headline}</h2>
          {card.summary && <p className="line-clamp-3 text-ui text-muted">{card.summary}</p>}
        </div>
        <Meta card={card} lang={lang} />
      </Wrapper>
    );

  return (
    <Wrapper {...wrapperProps} dir="auto" className={cn("focus-ring group flex w-full gap-4 rounded-control py-5 text-start", className)}>
      <div className="flex min-w-0 flex-1 flex-col gap-1.5">
        {fromCommunity && <div>{fromCommunity}</div>}
        <h3 className="text-title decoration-line decoration-2 underline-offset-4 group-hover:underline">{card.headline}</h3>
        {card.summary && <p className="line-clamp-2 text-ui text-muted">{card.summary}</p>}
        <div className="mt-1.5"><Meta card={card} lang={lang} /></div>
      </div>
      {img}
    </Wrapper>
  );
}
