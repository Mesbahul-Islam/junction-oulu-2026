import { useQuery } from "@tanstack/react-query";

import { getFeed, getSaved } from "../api";

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

export function useSaved() {
  return useQuery({ queryKey: ["saved"], queryFn: getSaved });
}
