import { cn } from "@/lib/utils";

export function Spinner({ className }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={cn("inline-block h-6 w-6 animate-spin rounded-full border-2 border-line border-t-accent", className)}
    />
  );
}
