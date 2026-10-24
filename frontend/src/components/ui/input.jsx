import * as React from "react";

import { cn } from "@/lib/utils";

const base =
  "w-full rounded-control border border-line bg-surface px-3 text-ui md:text-[14px] text-ink placeholder:text-muted/70 " +
  "outline-none transition-colors duration-150 hover:border-ink/25 " +
  "focus-visible:border-ink focus-visible:ring-1 focus-visible:ring-ink " +
  "aria-[invalid=true]:border-danger disabled:cursor-not-allowed disabled:opacity-50";

export const Input = React.forwardRef(function Input({ className, ...props }, ref) {
  return <input ref={ref} className={cn(base, "h-11 md:h-9 [@media(pointer:coarse)]:min-h-11", className)} {...props} />;
});

export const Textarea = React.forwardRef(function Textarea({ className, ...props }, ref) {
  return <textarea ref={ref} className={cn(base, "min-h-[120px] resize-y py-3", className)} {...props} />;
});
