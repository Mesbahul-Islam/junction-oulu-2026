import { CircleAlert, Inbox } from "lucide-react";

import { Button, Skeleton } from "@/components/ui";
import { cn } from "@/lib/utils";

/** Empty is an invitation to act: say what goes here and how to get it. */
export function EmptyState({ icon: Icon = Inbox, title, children, action, className }) {
  return (
    <div className={cn("flex flex-col items-center gap-3 px-6 py-14 text-center", className)}>
      <span className="grid h-12 w-12 place-items-center rounded-full bg-sunk text-muted"><Icon size={22} /></span>
      <h3 className="text-title">{title}</h3>
      {children && <p className="max-w-xs text-ui text-muted">{children}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

/** Say what failed and offer the fix; no apologies. */
export function ErrorState({ title = "This didn't load", error, onRetry, className }) {
  return (
    <div role="alert" className={cn("flex flex-col items-center gap-3 px-6 py-14 text-center", className)}>
      <span className="grid h-12 w-12 place-items-center rounded-full bg-danger-weak text-danger"><CircleAlert size={22} /></span>
      <h3 className="text-title">{title}</h3>
      <p className="max-w-xs text-ui text-muted">{error?.message ? `${error.message}. ` : ""}Check your connection and try again.</p>
      {onRetry && <Button variant="secondary" size="sm" onClick={onRetry}>Try again</Button>}
    </div>
  );
}

export function ListSkeleton({ rows = 4 }) {
  return (
    <div className="divide-y divide-line" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-4 py-5">
          <div className="flex flex-1 flex-col gap-2.5">
            <Skeleton className="h-4 w-11/12" />
            <Skeleton className="h-4 w-3/5" />
            <Skeleton className="mt-2 h-5 w-28 rounded-pill" />
          </div>
          <Skeleton className="h-[88px] w-[88px] rounded-control" />
        </div>
      ))}
    </div>
  );
}

/** Standard loading / error / empty for a React Query result or plain async state. */
export function QueryBoundary({ query, children, loading, empty, isEmpty, isLoading, error, data } = {}) {
  const q = query || {};
  const pending = isLoading ?? q.isPending ?? q.isLoading ?? false;
  const err = error ?? q.error ?? null;
  const items = data ?? q.data;
  if (pending) return loading ?? <ListSkeleton />;
  if (err) return <ErrorState error={err} onRetry={q.refetch ? () => q.refetch() : undefined} />;
  const blank = isEmpty ? isEmpty(items) : Array.isArray(items) && items.length === 0;
  if (blank) return empty ?? <EmptyState title="Nothing here yet" />;
  return typeof children === "function" ? children(items) : children;
}
