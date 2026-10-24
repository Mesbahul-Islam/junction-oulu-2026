import * as RadioGroup from "@radix-ui/react-radio-group";
import * as ToggleGroup from "@radix-ui/react-toggle-group";
import { Check } from "lucide-react";

import { cn } from "@/lib/utils";

// Shared selectable-card look. Radix sets data-state (checked / on). Selection is ink:
// it's the reader's own choice, not a provenance signal.
const cardCls =
  "group relative flex w-full items-center gap-3 rounded-card border border-line bg-surface p-4 text-left " +
  "transition-[border-color,box-shadow] duration-150 ease-kajo hover:border-ink/25 focus-ring " +
  "data-[state=checked]:border-ink data-[state=checked]:shadow-[inset_0_0_0_1px_hsl(var(--ink-hsl))] " +
  "data-[state=on]:border-ink data-[state=on]:shadow-[inset_0_0_0_1px_hsl(var(--ink-hsl))]";

function Tick({ square }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "grid h-5 w-5 shrink-0 place-items-center border border-line text-on-ink transition-colors duration-150",
        square ? "rounded-[6px]" : "rounded-full",
        "group-data-[state=checked]:border-ink group-data-[state=checked]:bg-ink group-data-[state=on]:border-ink group-data-[state=on]:bg-ink",
      )}
    >
      <Check size={12} strokeWidth={3} className="opacity-0 group-data-[state=checked]:opacity-100 group-data-[state=on]:opacity-100" />
    </span>
  );
}

const layout = (columns) => (columns ? cn("grid gap-2", columns) : "flex flex-col gap-2");
const content = (o, renderOption) => (
  <span className="min-w-0 flex-1">{renderOption ? renderOption(o) : <span className="text-title text-ink">{o.label}</span>}</span>
);

/** Single-select cards. `columns` takes grid classes (e.g. "grid-cols-2"); omit for a stacked list. */
export function RadioCards({ value, onValueChange, options, renderOption, columns, className, ...props }) {
  return (
    <RadioGroup.Root value={value} onValueChange={onValueChange} className={cn(layout(columns), className)} {...props}>
      {options.map((o) => (
        <RadioGroup.Item key={o.value} value={o.value} className={cardCls}>
          {content(o, renderOption)}
          <Tick />
        </RadioGroup.Item>
      ))}
    </RadioGroup.Root>
  );
}

/** Multi-select pills (topics, interests). Selected = filled ink. Options: { value, label, icon? }. */
export function ToggleChips({ value, onValueChange, options, className, ...props }) {
  return (
    <ToggleGroup.Root type="multiple" value={value} onValueChange={onValueChange} className={cn("flex flex-wrap gap-2", className)} {...props}>
      {options.map(({ value: v, label, icon: Icon }) => (
        <ToggleGroup.Item
          key={v}
          value={v}
          className="focus-ring inline-flex h-11 items-center gap-2 rounded-pill border border-line bg-surface px-4 text-ui text-ink transition-colors duration-150 ease-kajo hover:border-ink/30 data-[state=on]:border-ink data-[state=on]:bg-ink data-[state=on]:text-on-ink"
        >
          {Icon && <Icon size={17} strokeWidth={1.8} />}
          {label}
        </ToggleGroup.Item>
      ))}
    </ToggleGroup.Root>
  );
}

/** Multi-select cards. `value` is an array of selected values. */
export function ToggleCards({ value, onValueChange, options, renderOption, columns, className, ...props }) {
  return (
    <ToggleGroup.Root type="multiple" value={value} onValueChange={onValueChange} className={cn(layout(columns), className)} {...props}>
      {options.map((o) => (
        <ToggleGroup.Item key={o.value} value={o.value} className={cardCls}>
          {content(o, renderOption)}
          <Tick square />
        </ToggleGroup.Item>
      ))}
    </ToggleGroup.Root>
  );
}
