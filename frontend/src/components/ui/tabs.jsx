import * as TabsPrimitive from "@radix-ui/react-tabs";

import { cn } from "@/lib/utils";

export const Tabs = TabsPrimitive.Root;
export const TabsContent = TabsPrimitive.Content;

/** Underline tabs on a hairline. */
export function TabsList({ className, ...props }) {
  return <TabsPrimitive.List className={cn("flex gap-6 border-b border-line", className)} {...props} />;
}

export function TabsTrigger({ className, ...props }) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        "focus-ring relative -mb-px whitespace-nowrap border-b-2 border-transparent pb-3 pt-1 text-ui font-medium text-muted transition-colors",
        "hover:text-ink data-[state=active]:border-ink data-[state=active]:text-ink",
        className,
      )}
      {...props}
    />
  );
}
