import { QueryClient } from "@tanstack/react-query";

// One client for the app. staleTime keeps feed/community lists from refetching on every
// remount; 401s already clear the token in lib/api.js, so don't retry auth failures.
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: (count, err) => err?.status !== 401 && count < 2,
    },
  },
});
