import { useQuery } from "@tanstack/react-query";

import { getMyTrust, getTrustedVoices } from "./api";

/** isTrusted(userId, communitySlug): is this member an approved trusted voice there? The list is
 *  small and changes rarely, so it is fetched once and kept for 10 minutes. */
export function useTrustedVoices() {
  const { data } = useQuery({ queryKey: ["trusted-voices"], queryFn: getTrustedVoices, staleTime: 10 * 60e3 });
  const keys = new Set((data || []).map((v) => `${v.user}:${v.community_slug}`));
  return (userId, slug) => keys.has(`${userId}:${slug}`);
}

export function useMyTrust() {
  return useQuery({ queryKey: ["my-trust"], queryFn: getMyTrust, staleTime: 60e3 });
}
