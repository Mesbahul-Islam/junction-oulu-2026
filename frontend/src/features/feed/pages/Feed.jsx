import { useQuery } from "@tanstack/react-query";
import { Compass, Languages, ListPlus, MapPin, MessageCircleQuestion, Newspaper, Users } from "lucide-react";
import { useEffect, useRef } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { Button, Meter, Spinner } from "@/components/ui";
import { Column, ColumnTitle, EmptyState, FilterBar, FilterChip, QueryBoundary, RailPanel } from "@/components/patterns";
import { useAuth } from "@/features/auth/AuthProvider";
import { getCommunityNews } from "@/features/communities/api";
import { useShortlist } from "@/features/shortlist/hooks/useShortlist";
import { languageName, topicIcon, topicLabel } from "@/lib/i18n";
import { StoryRow } from "../components/StoryRow";
import { ProposalRow } from "@/features/shortlist/components/ProposalRow";
import { ArrivalBlock, ArrivalList, arrivalTitle, CommunityPostList, CommunityPostRow, NextStoryRow } from "../components/TimelineExtras";
import { useArrival, useFeedArea, useTimeline } from "../hooks/useFeed";

/** Header line for the reader's town: "News from Oulu", or "Kemi · news from nearby Oulu" while
 *  we don't cover their town yet (onboarding explains why). */
function areaText(area) {
  if (!area?.news_from?.length) return "";
  const from = area.news_from.join(", ");
  return area.local ? `News from ${from}` : `${area.town} · news from nearby ${from}`;
}

/** Story cards with community posts and one open proposal mixed in at fixed slots. */
function mix(stories, posts, proposal, complete) {
  const extras = [
    [1, posts[0] && { post: posts[0] }],
    [3, proposal && { proposal }],
    [6, posts[1] && { post: posts[1] }],
    [10, posts[2] && { post: posts[2] }],
  ].filter(([, x]) => x);
  const rows = [];
  stories.forEach((story, i) => {
    rows.push({ story, i });
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

  const setParam = (key, value) => setParams((p) => {
    const next = new URLSearchParams(p);
    if (value) next.set(key, value); else next.delete(key);
    return next;
  }, { replace: true });

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
  const inYourLanguage = stories.filter((s) => s.in_your_language).length;

  // From 1024px the arrival guide, the open vote and community posts sit beside the timeline
  // instead of inside it; below that they stay mixed in (the inline copies are lg:hidden).
  const rail = (
    <>
      {lang && stories.length > 0 && (
        <RailPanel icon={Languages} title={`Reading in ${languageName(lang)}`}>
          <Meter label={`${inYourLanguage} of ${stories.length} loaded stories`} value={inYourLanguage} max={stories.length} display="" tone="newsroom" />
          {inYourLanguage < stories.length && (
            <p className="mt-2 text-caption text-muted">The rest show in the original until an editor approves the translation.</p>
          )}
        </RailPanel>
      )}
      {arrivalData && (
        <RailPanel icon={Compass} title={arrivalTitle(arrivalData)}>
          <ArrivalList arrival={arrivalData} />
        </RailPanel>
      )}
      {proposal && (
        <RailPanel icon={ListPlus} title="Next stories" action={<Link to="/vote" className="focus-ring rounded-control normal-case tracking-normal hover:text-ink">{open.length > 1 ? `See all ${open.length}` : "See all"}</Link>}>
          <ProposalRow item={proposal} canVote={shortlist.data?.member} detail={false} stacked />
        </RailPanel>
      )}
      {posts.length > 0 && (
        <RailPanel icon={Users} title="From your communities" action={<Link to="/communities" className="focus-ring rounded-control normal-case tracking-normal hover:text-ink">Open</Link>}>
          <CommunityPostList posts={posts} lang={lang} />
        </RailPanel>
      )}
    </>
  );

  return (
    <Column
      rail={rail}
      header={
        <>
          <ColumnTitle
            title="For You"
            subtitle={areaLine ? <>{today}<span className="mt-0.5 flex items-center gap-1"><MapPin size={13} className="shrink-0" />{areaLine}</span></> : today}
            aside={
              <>
                {lang && <span className="hidden sm:inline lg:hidden">Reading in {languageName(lang)}</span>}
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

      {arrivalData && <div className="lg:hidden"><ArrivalBlock arrival={arrivalData} /></div>}

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
            <StoryRow
              key={`s${r.story.id}`}
              card={r.story}
              lang={lang}
              lead={r.i === 0}
              detail={r.i < 3}
            />
          ) : (
            <div key={r.post ? `p${r.post.id}` : `v${r.proposal.id}`} className="lg:hidden">
              {r.post ? (
                <CommunityPostRow post={r.post} lang={lang} />
              ) : (
                <NextStoryRow item={r.proposal} total={open.length} canVote={shortlist.data?.member} />
              )}
            </div>
          ),
        )}
        <div ref={endRef} className="grid place-items-center py-10">
          {timeline.isFetchingNextPage ? <Spinner /> : !timeline.hasNextPage && stories.length > 0 && (
            <p className="text-meta text-muted">You're up to date.</p>
          )}
        </div>
      </QueryBoundary>
    </Column>
  );
}
