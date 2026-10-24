import { useQuery } from "@tanstack/react-query";

import { getCommunities, getRecommendedCommunities } from "../api";

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
