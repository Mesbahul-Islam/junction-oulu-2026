import { useInfiniteQuery, useQuery } from "@tanstack/react-query";

import { getCommunities, getCommunityNews, getGroupPosts, getPage, getPost, getRecommendedCommunities, getReplies } from "../api";

// All groups + the profile-matched suggestions, fetched together. `refetch` re-pulls both
// after a join/leave. ponytail: plain refetch, not per-mutation cache surgery — the list is small.
export function useCommunities() {
  return useQuery({
    queryKey: ["communities"],
    queryFn: async () => {
      const [all, suggested] = await Promise.all([getCommunities(), getRecommendedCommunities()]);
      return { all, suggested };
    },
  });
}

// Posts from all the reader's communities, or one community's (`slug`), newest first.
export function usePosts(slug) {
  return useInfiniteQuery({
    queryKey: ["posts", slug || "all"],
    queryFn: ({ pageParam }) => (pageParam ? getPage(pageParam) : slug ? getGroupPosts(slug) : getCommunityNews()),
    initialPageParam: null,
    getNextPageParam: (last) => last.next || undefined,
    select: (d) => d.pages.flatMap((p) => p.results ?? p),
  });
}

export function usePost(slug, id, placeholder) {
  return useQuery({ queryKey: ["post", Number(id)], queryFn: () => getPost(slug, id), placeholderData: placeholder });
}

export function useReplies(slug, id) {
  return useQuery({ queryKey: ["replies", Number(id)], queryFn: () => getReplies(slug, id), select: (d) => d.results ?? d });
}
