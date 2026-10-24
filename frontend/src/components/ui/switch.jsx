import * as SwitchPrimitive from "@radix-ui/react-switch";

import { cn } from "@/lib/utils";

export function Switch({ className, ...props }) {
  return (
    <SwitchPrimitive.Root
      className={cn(
        "focus-ring peer inline-flex h-6 w-10 shrink-0 items-center rounded-pill bg-line p-0.5 transition-colors duration-150 data-[state=checked]:bg-ink disabled:opacity-40",
        className,
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb className="block h-5 w-5 rounded-full bg-surface shadow-soft transition-transform duration-200 ease-kajo data-[state=checked]:translate-x-4 rtl:data-[state=checked]:-translate-x-4" />
    </SwitchPrimitive.Root>
  );
}
