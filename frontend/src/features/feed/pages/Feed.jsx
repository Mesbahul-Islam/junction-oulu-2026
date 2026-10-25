import { useQuery } from "@tanstack/react-query";
import { MapPin, MessageCircleQuestion, Newspaper } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { Button, Spinner } from "@/components/ui";
import { Column, ColumnTitle, EmptyState, FilterBar, FilterChip, QueryBoundary, SidePeek, useCanPeek } from "@/components/patterns";
import { useAuth } from "@/features/auth/AuthProvider";
import { getCommunityNews } from "@/features/communities/api";
import { useShortlist } from "@/features/shortlist/hooks/useShortlist";
import { languageName, topicIcon, topicLabel } from "@/lib/i18n";
import { StoryRow } from "../components/StoryRow";
import { StoryView } from "../components/StoryView";
import { ArrivalBlock, CommunityPostRow, NextStoryRow } from "../components/TimelineExtras";
import { useArrival, useFeedArea, useTimeline } from "../hooks/useFeed";

/** Story cards with community posts and one open proposal mixed in at fixed slots. */
/** Header line for the reader's town: "News from Oulu", or "Kemi · news from nearby Oulu" while
 *  we don't cover their town yet (onboarding explains why). */
function areaText(area) {
  if (!area?.news_from?.length) return "";
  const from = area.news_from.join(", ");
  return area.local ? `News from ${from}` : `${area.town} · news from nearby ${from}`;
}

function mix(stories, posts, proposal, complete) {
  const extras = [
    [1, posts[0] && { post: posts[0] }],
    [3, proposal && { proposal }],
    [6, posts[1] && { post: posts[1] }],
    [10, posts[2] && { post: posts[2] }],
  ].filter(([, x]) => x);
  const rows = [];
  stories.forEach((story, i) => {
    rows.push({ story });
    extras.filter(([at]) => at === i).forEach(([, x]) => rows.push(x));
  });
  // A short feed still shows the first community post and the proposal, at the end.
  if (complete) extras.filter(([at]) => at >= stories.length).slice(0, 2).forEach(([, x]) => rows.push(x));
  return rows;
}

export default function Feed() {
  const { me } = useAuth();
  const lang = me?.preferred_language;
  const [params, setParams] = useSearchParams();
  const tag = params.get("tag");
  const peekId = params.get("story");
  const canPeek = useCanPeek();

  const timeline = useTimeline(tag);
  const area = useFeedArea(tag);
  const arrival = useArrival(!!me?.arrival_date && !tag);
  const news = useQuery({ queryKey: ["community-news"], queryFn: getCommunityNews, enabled: !tag });
  const shortlist = useShortlist();

  const stories = timeline.data || [];
  const posts = tag ? [] : (news.data?.results ?? news.data ?? []).filter((p) => !p.parent && p.status === "visible" && !p.is_mine).slice(0, 3);
  const open = tag ? [] : shortlist.data?.open || [];
  const proposal = open.find((x) => !x.voted) || open[0];
  const rows = mix(stories, posts, proposal, !timeline.hasNextPage);

  const [peekCard, setPeekCard] = useState(null);
  const setParam = (key, value) => setParams((p) => {
    const next = new URLSearchParams(p);
    if (value) next.set(key, value); else next.delete(key);
    return next;
  }, { replace: key === "tag" });
  const openStory = canPeek ? (card) => { setPeekCard(card); setParam("story", card.id); } : undefined;
  const closePeek = () => setParam("story", null);
  const peekCardFor = peekCard?.id === Number(peekId) ? peekCard : stories.find((s) => s.id === Number(peekId));

  // Load the next page when the end of the list comes into view.
  const endRef = useRef(null);
  useEffect(() => {
    if (!endRef.current || !timeline.hasNextPage) return;
    const io = new IntersectionObserver(([e]) => e.isIntersecting && !timeline.isFetchingNextPage && timeline.fetchNextPage(), { rootMargin: "600px" });
    io.observe(endRef.current);
    return () => io.disconnect();
  }, [timeline]);

  const today = new Date().toLocaleDateString(lang, { weekday: "long", day: "numeric", month: "long" });
  const areaLine = areaText(area.data);
  const interests = me?.profile?.interests || [];
  const arrivalData = arrival.data?.results?.length ? arrival.data : null;

  return (
    <Column
      header={
        <>
          <ColumnTitle
            title="For You"
            subtitle={areaLine ? <>{today}<span className="mt-0.5 flex items-center gap-1"><MapPin size={13} className="shrink-0" />{areaLine}</span></> : today}
            aside={
              <>
                {lang && <span className="hidden sm:inline lg:pb-0.5">Reading in {languageName(lang)}</span>}
                {/* The sidebar has Ask on desktop; phones and tablets get it here. */}
                <Button asChild variant="secondary" size="sm" className="lg:hidden">
                  <Link to="/create"><MessageCircleQuestion size={15} />Ask</Link>
                </Button>
              </>
            }
          />
          {interests.length > 0 && (
            <FilterBar label="Topics">
              <FilterChip active={!tag} onClick={() => setParam("tag", null)}>All</FilterChip>
              {interests.map((t) => (
                <FilterChip key={t} active={tag === t} icon={topicIcon(t)} onClick={() => setParam("tag", tag === t ? null : t)}>{topicLabel(t)}</FilterChip>
              ))}
            </FilterBar>
          )}
        </>
      }
    >

      {arrivalData && <ArrivalBlock arrival={arrivalData} onOpen={openStory} />}

      <QueryBoundary
        query={timeline}
        isEmpty={(d) => !d?.length}
        empty={
          <EmptyState
            icon={Newspaper}
            title={tag ? `No ${topicLabel(tag).toLowerCase()} stories yet` : "No stories yet"}
            action={tag && <Button variant="secondary" size="sm" onClick={() => setParam("tag", null)}>Show all stories</Button>}
          >
            Stories appear here once an editor has checked them.
          </EmptyState>
        }
      >
        {rows.map((r) =>
          r.story ? (
            <StoryRow key={`s${r.story.id}`} card={r.story} lang={lang} onOpen={openStory} active={String(r.story.id) === peekId} />
          ) : r.post ? (
            <CommunityPostRow key={`p${r.post.id}`} post={r.post} lang={lang} />
          ) : (
            <NextStoryRow key={`v${r.proposal.id}`} item={r.proposal} total={open.length} canVote={shortlist.data?.member} />
          ),
        )}
        <div ref={endRef} className="grid place-items-center py-10">
          {timeline.isFetchingNextPage ? <Spinner /> : !timeline.hasNextPage && stories.length > 0 && (
            <p className="text-meta text-muted">You're up to date.</p>
          )}
        </div>
      </QueryBoundary>

      {canPeek && peekId && (
        <SidePeek id={peekId} label="Story" href={`/story/${peekId}`} state={peekCardFor} onClose={closePeek}>
          <StoryView id={peekId} card={peekCardFor} ranking={peekCardFor?.ranking} lang={lang} onReported={closePeek} />
        </SidePeek>
      )}
    </Column>
  );
}
