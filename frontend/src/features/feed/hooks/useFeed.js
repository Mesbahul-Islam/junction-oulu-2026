import { useInfiniteQuery, useQuery } from "@tanstack/react-query";

import { getArrival, getFeed, getSaved } from "../api";

const PAGE = 20;

// Reviewed stories, optionally filtered by topic tag. `select` unwraps the paginated
// envelope so callers get the array. Pass enabled:false to hold the query (e.g. no topic yet).
export function useFeed({ tag, limit = 30, enabled = true } = {}) {
  return useQuery({
    queryKey: ["feed", { tag: tag || null, limit }],
    queryFn: () => getFeed({ tag, limit }),
    select: (d) => d.results,
    enabled,
  });
}

// The Today timeline: ranked pages of PAGE cards (offset pagination over the ranked window).
const timeline = (tag) => ({
  queryKey: ["timeline", tag || null],
  queryFn: ({ pageParam }) => getFeed({ tag, limit: PAGE, offset: pageParam }),
  initialPageParam: 0,
  getNextPageParam: (last, pages) => (last.next ? pages.length * PAGE : undefined),
});

export function useTimeline(tag) {
  return useInfiniteQuery({ ...timeline(tag), select: (d) => d.pages.flatMap((p) => p.results) });
}

// Which town the timeline is for: {town, news_from: [...], local} or null. Shares the timeline's cache.
export function useFeedArea(tag) {
  return useInfiniteQuery({ ...timeline(tag), select: (d) => d.pages[0]?.area ?? null });
}

// Newcomer sequence for the reader's current arrival bucket; empty for everyone else.
export function useArrival(enabled) {
  return useQuery({ queryKey: ["arrival"], queryFn: getArrival, enabled });
}

export function useSaved() {
  return useQuery({ queryKey: ["saved"], queryFn: getSaved });
}
