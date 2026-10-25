import { ArrowRight, Compass, Heart, Languages, ListPlus, MessageCircle, Users } from "lucide-react";
import { Link } from "react-router-dom";

import { Avatar, Badge } from "@/components/ui";
import { languageName, timeAgo } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { ProposalRow } from "@/features/shortlist/components/ProposalRow";

/** Section label inside the timeline: says where the next item comes from. */
function Kicker({ icon: Icon, children, to, action }) {
  return (
    <div className="flex items-center gap-2 text-caption font-semibold uppercase tracking-wide text-muted">
      <Icon size={13} />
      <span className="flex-1">{children}</span>
      {to && <Link to={to} className="focus-ring rounded-control normal-case tracking-normal text-muted hover:text-ink">{action}</Link>}
    </div>
  );
}

/** A member's post, mixed into the timeline. Cloudberry = a member's words, not reviewed. */
export function CommunityPostRow({ post, lang }) {
  const text = post.translation?.text || post.body;
  return (
    <article className="border-b border-line bg-community-weak/25 px-4 py-5 sm:px-6">
      <Kicker icon={Users} to="/communities" action="Open community">From {post.community_name}</Kicker>
      <div className="mt-3 flex gap-3">
        <Avatar name={post.author_name} size="sm" community />
        <div className="min-w-0 flex-1" dir="auto">
          <p className="flex flex-wrap items-center gap-x-2 text-meta">
            <span className="font-medium text-ink">{post.author_name}</span>
            <span className="text-muted">{timeAgo(post.created_at, lang)}</span>
            {post.kind === "announcement" && <Badge tone="community">Announcement</Badge>}
          </p>
          <p className="mt-1 text-ui text-ink" lang={post.translation?.language || post.language}>{text}</p>
          <p className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-caption text-muted">
            <span>A member's words, not checked by editors</span>
            {post.translation && <span className="inline-flex items-center gap-1"><Languages size={12} />Machine-translated from {languageName(post.translation.from_language)}</span>}
            <span className="inline-flex items-center gap-1"><Heart size={12} />{post.like_count}</span>
            <span className="inline-flex items-center gap-1"><MessageCircle size={12} />{post.reply_count}</span>
          </p>
        </div>
      </div>
    </article>
  );
}

/** One open proposal from Next stories, votable in place. */
export function NextStoryRow({ item, total, canVote }) {
  return (
    <article className="border-b border-line px-4 py-5 sm:px-6">
      <Kicker icon={ListPlus} to="/vote" action={total > 1 ? `See all ${total}` : "See all"}>Next stories · vote for what we cover</Kicker>
      <div className="mt-3"><ProposalRow item={item} canVote={canVote} detail={false} /></div>
    </article>
  );
}

const BUCKET = { first_48h: "Your first 48 hours", first_week: "Your first week", first_month: "Your first month" };

export const arrivalTitle = (arrival) =>
  `${BUCKET[arrival.bucket] || "Getting started"} in Oulu${arrival.days_since_arrival != null ? ` · day ${arrival.days_since_arrival + 1}` : ""}`;

/** The first three stories of the newcomer sequence, numbered. */
export function ArrivalList({ arrival, onOpen }) {
  return (
    <ol className="flex flex-col">
      {arrival.results.slice(0, 3).map((s, i) => (
        <li key={s.id}>
          <Link
            to={`/story/${s.id}`}
            state={s}
            onClick={(e) => onOpen && !e.metaKey && !e.ctrlKey && (e.preventDefault(), onOpen(s))}
            className={cn("focus-ring group flex items-center gap-3 rounded-control py-2", i > 0 && "border-t border-line")}
          >
            <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-sunk text-caption font-semibold text-muted">{i + 1}</span>
            <span className="min-w-0 flex-1 truncate text-ui group-hover:underline" dir="auto">{s.headline}</span>
            <ArrowRight size={15} className="text-muted rtl:rotate-180" />
          </Link>
        </li>
      ))}
    </ol>
  );
}

/** Newcomer sequence: what to sort out now, by days since arrival. Only shown when it has stories. */
export function ArrivalBlock({ arrival, onOpen }) {
  return (
    <section className="border-b border-line px-4 py-5 sm:px-6">
      <Kicker icon={Compass}>{arrivalTitle(arrival)}</Kicker>
      <div className="mt-3"><ArrivalList arrival={arrival} onOpen={onOpen} /></div>
    </section>
  );
}

/** Community posts for a side rail: short, clamped, cloudberry avatars. */
export function CommunityPostList({ posts, lang }) {
  return (
    <>
      <ul className="flex flex-col divide-y divide-line">
        {posts.map((post) => (
          <li key={post.id} className="flex gap-3 py-3 first:pt-0" dir="auto">
            <Avatar name={post.author_name} size="sm" community />
            <div className="min-w-0 flex-1">
              <p className="flex items-baseline gap-2 text-meta">
                <span className="truncate font-medium text-ink">{post.author_name}</span>
                <span className="shrink-0 text-caption text-muted">{timeAgo(post.created_at, lang)}</span>
              </p>
              <p className="mt-0.5 line-clamp-3 text-meta text-ink" lang={post.translation?.language || post.language}>{post.translation?.text || post.body}</p>
              <p className="mt-1 flex items-center gap-3 text-caption text-muted">
                <span className="truncate">{post.community_name}</span>
                <span className="inline-flex items-center gap-1"><Heart size={12} />{post.like_count}</span>
                <span className="inline-flex items-center gap-1"><MessageCircle size={12} />{post.reply_count}</span>
              </p>
            </div>
          </li>
        ))}
      </ul>
      <p className="mt-1 text-caption text-muted">Members' words, not checked by editors.</p>
    </>
  );
}
