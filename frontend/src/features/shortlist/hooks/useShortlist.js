import { useQuery, useQueryClient } from "@tanstack/react-query";

import { toast } from "@/components/ui";
import { getShortlist, voteStory } from "../api";

// { open: [...], covered: [...], member: bool } — open is most-voted first.
export function useShortlist() {
  return useQuery({ queryKey: ["shortlist"], queryFn: getShortlist });
}

/** Vote / take back a vote on one proposal; the server's count replaces ours. */
export function useVote() {
  const queryClient = useQueryClient();
  return async (item) => {
    try {
      const res = await voteStory(item.id, !item.voted);
      queryClient.setQueryData(["shortlist"], (d) =>
        ({ ...d, open: d.open.map((x) => (x.id === item.id ? { ...x, votes: res.votes, voted: res.voted } : x)) }));
    } catch (e) {
      toast({ title: "Your vote didn't count", description: e.message, tone: "danger" });
    }
  };
}
