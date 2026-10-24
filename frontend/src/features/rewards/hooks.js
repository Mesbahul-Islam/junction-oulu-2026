import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { cancelPlan, getMyRewards, redeemPerk, subscribePlan } from "./api";

export function useMyRewards() {
  return useQuery({ queryKey: ["my-rewards"], queryFn: getMyRewards, staleTime: 60e3 });
}

// Every change refreshes the rewards page data (codes, plan).
function useRewardsMutation(mutationFn) {
  const qc = useQueryClient();
  return useMutation({ mutationFn, onSuccess: () => qc.invalidateQueries({ queryKey: ["my-rewards"] }) });
}

export const useRedeem = () => useRewardsMutation(redeemPerk);
export const useSubscribe = () => useRewardsMutation(subscribePlan);
export const useCancelPlan = () => useRewardsMutation(cancelPlan);
