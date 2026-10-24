import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva } from "class-variance-authority";

import { cn } from "@/lib/utils";

// Primary actions are ink, not blue: blue is reserved for "the newsroom vouches for this".
// Compact on desktop (Notion density), roomy on phones; any touch screen gets 44px targets.
const buttonVariants = cva(
  "focus-ring inline-flex shrink-0 select-none items-center justify-center gap-2 whitespace-nowrap rounded-control font-medium " +
    "transition-[background-color,color,border-color] duration-150 ease-kajo " +
    "[@media(pointer:coarse)]:min-h-11 disabled:pointer-events-none disabled:opacity-40 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary: "bg-ink text-on-ink hover:bg-ink/85",
        secondary: "border border-line bg-surface text-ink hover:bg-ink/5",
        ghost: "text-ink hover:bg-ink/5",
        link: "text-ink underline decoration-line decoration-1 underline-offset-[3px] hover:decoration-ink [@media(pointer:coarse)]:min-h-0",
        danger: "bg-danger text-on-ink hover:bg-danger/90",
      },
      size: {
        sm: "h-9 px-2.5 text-meta md:h-7",
        md: "h-11 px-3 text-ui md:h-8 md:text-[14px]",
        lg: "h-12 px-4 text-ui md:h-9 md:text-[14px]",
        icon: "h-11 w-11 md:h-8 md:w-8 [@media(pointer:coarse)]:min-w-11",
        "icon-sm": "h-9 w-9 md:h-7 md:w-7 [@media(pointer:coarse)]:min-w-11",
      },
      block: { true: "w-full" },
    },
    compoundVariants: [{ variant: "link", className: "h-auto px-0 md:h-auto" }],
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export const Button = React.forwardRef(function Button({ className, variant, size, block, asChild = false, ...props }, ref) {
  const Comp = asChild ? Slot : "button";
  return <Comp ref={ref} className={cn(buttonVariants({ variant, size, block }), className)} {...props} />;
});

export { buttonVariants };
