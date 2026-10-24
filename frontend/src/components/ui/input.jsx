import * as React from "react";

import { cn } from "@/lib/utils";

export const Input = React.forwardRef(function Input({ className, ...props }, ref) {
  return (
    <input
      ref={ref}
      className={cn(
        "h-12 w-full rounded-md border border-line bg-surface px-3.5 text-[15px] text-ink",
        "placeholder:text-muted/70 outline-none transition-colors",
        "focus-visible:border-accent focus-visible:ring-4 focus-visible:ring-accent/15",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
});

export const Textarea = React.forwardRef(function Textarea({ className, ...props }, ref) {
  return (
    <textarea
      ref={ref}
      className={cn(
        "min-h-[120px] w-full resize-y rounded-md border border-line bg-surface px-3.5 py-3 text-[15px] text-ink",
        "placeholder:text-muted/70 outline-none transition-colors",
        "focus-visible:border-accent focus-visible:ring-4 focus-visible:ring-accent/15",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
});
