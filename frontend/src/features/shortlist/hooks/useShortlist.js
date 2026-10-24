import { useQuery } from "@tanstack/react-query";

import { getShortlist } from "../api";

export function useShortlist() {
  return useQuery({ queryKey: ["shortlist"], queryFn: getShortlist });
}
