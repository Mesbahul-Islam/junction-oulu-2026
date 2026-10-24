import { QueryClientProvider } from "@tanstack/react-query";

import { Toaster } from "@/components/ui";
import { AuthProvider } from "@/features/auth/AuthProvider";

import { queryClient } from "./queryClient";

// Every app-wide provider lives here, outermost first. New global state (theme, etc.)
// gets added as another wrapper — nowhere else.
export function Providers({ children }) {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        {children}
        <Toaster />
      </AuthProvider>
    </QueryClientProvider>
  );
}
