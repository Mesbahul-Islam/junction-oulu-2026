import * as RadioGroup from "@radix-ui/react-radio-group";
import * as ToggleGroup from "@radix-ui/react-toggle-group";
import { Check } from "lucide-react";

import { cn } from "@/lib/utils";

// Shared selectable-card look. Radix sets data-state (checked/on) on the item.
const cardCls =
  "group relative flex w-full items-center gap-3 rounded-lg border bg-surface p-4 text-left transition-colors " +
  "border-line hover:border-ink/20 outline-none " +
  "focus-visible:ring-4 focus-visible:ring-accent/15 " +
  "data-[state=checked]:border-accent data-[state=checked]:bg-accent-weak " +
  "data-[state=on]:border-accent data-[state=on]:bg-accent-weak";

const tick =
  "flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-line text-accent transition " +
  "group-data-[state=checked]:border-accent group-data-[state=checked]:bg-accent group-data-[state=checked]:text-accent-ink " +
  "group-data-[state=on]:border-accent group-data-[state=on]:bg-accent group-data-[state=on]:text-accent-ink";

function Tick() {
  return (
    <span className={tick} aria-hidden="true">
      <Check size={13} strokeWidth={3} className="opacity-0 group-data-[state=checked]:opacity-100 group-data-[state=on]:opacity-100" />
    </span>
  );
}

/** Single-select list/grid of cards. `columns` sets a responsive grid; omit for a stacked list. */
export function RadioCards({ value, onValueChange, options, renderOption, columns, className }) {
  return (
    <RadioGroup.Root
      value={value}
      onValueChange={onValueChange}
      className={cn(columns ? "grid gap-2.5" : "flex flex-col gap-2.5", columns, className)}
    >
      {options.map((o) => (
        <RadioGroup.Item key={o.value} value={o.value} className={cardCls}>
          <span className="min-w-0 flex-1">{renderOption ? renderOption(o) : <span className="font-semibold text-ink">{o.label}</span>}</span>
          <Tick />
        </RadioGroup.Item>
      ))}
    </RadioGroup.Root>
  );
}

/** Multi-select grid/list of cards. `value` is an array of selected values. */
export function ToggleCards({ value, onValueChange, options, renderOption, columns, className }) {
  return (
    <ToggleGroup.Root
      type="multiple"
      value={value}
      onValueChange={onValueChange}
      className={cn(columns ? "grid gap-2.5" : "flex flex-col gap-2.5", columns, className)}
    >
      {options.map((o) => (
        <ToggleGroup.Item key={o.value} value={o.value} className={cardCls}>
          <span className="min-w-0 flex-1">{renderOption ? renderOption(o) : <span className="font-semibold text-ink">{o.label}</span>}</span>
          <Tick />
        </ToggleGroup.Item>
      ))}
    </ToggleGroup.Root>
  );
}
