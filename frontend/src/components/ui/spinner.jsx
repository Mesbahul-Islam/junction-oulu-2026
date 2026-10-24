import { cn } from "@/lib/utils";

export function Spinner({ className }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={cn("inline-block h-5 w-5 animate-spin rounded-full border-2 border-line border-t-ink", className)}
    />
  );
}

/** Placeholder block while content loads. Size it with className (h-*, w-*). */
export function Skeleton({ className, ...props }) {
  return <span aria-hidden="true" className={cn("block animate-pulse rounded-control bg-sunk", className)} {...props} />;
}
