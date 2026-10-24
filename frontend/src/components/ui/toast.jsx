import * as ToastPrimitive from "@radix-ui/react-toast";
import { CircleAlert, CircleCheck, X } from "lucide-react";
import { useSyncExternalStore } from "react";

import { cn } from "@/lib/utils";

// Tiny module store so any code (not just components) can call toast(). Replaces window.alert.
let toasts = [];
const listeners = new Set();
const emit = () => listeners.forEach((l) => l());
const subscribe = (l) => (listeners.add(l), () => listeners.delete(l));
let nextId = 0;

/** toast({ title, description?, tone?: "neutral" | "confirmed" | "danger" }) */
export function toast(t) {
  toasts = [...toasts, { id: ++nextId, tone: "neutral", ...t }];
  emit();
}
const dismiss = (id) => {
  toasts = toasts.filter((t) => t.id !== id);
  emit();
};

const ICON = { confirmed: CircleCheck, danger: CircleAlert };

/** Mount once (in Providers). */
export function Toaster() {
  const list = useSyncExternalStore(subscribe, () => toasts);
  return (
    <ToastPrimitive.Provider duration={5000}>
      {list.map(({ id, title, description, tone }) => {
        const Icon = ICON[tone];
        return (
          <ToastPrimitive.Root
            key={id}
            onOpenChange={(open) => !open && dismiss(id)}
            className={cn(
              "flex items-start gap-3 rounded-card bg-ink p-4 pr-3 font-sans text-on-ink shadow-float",
              "data-[state=open]:animate-in data-[state=open]:slide-in-from-bottom-4 data-[state=closed]:animate-out data-[state=closed]:fade-out-0",
              "data-[swipe=move]:translate-y-[var(--radix-toast-swipe-move-y)] data-[swipe=end]:animate-out",
            )}
          >
            {Icon && <Icon size={18} className={cn("mt-0.5 shrink-0", tone === "danger" ? "text-danger" : "text-confirmed")} />}
            <div className="flex min-w-0 flex-1 flex-col gap-0.5">
              <ToastPrimitive.Title className="text-ui font-medium">{title}</ToastPrimitive.Title>
              {description && <ToastPrimitive.Description className="text-meta opacity-75">{description}</ToastPrimitive.Description>}
            </div>
            <ToastPrimitive.Close className="focus-ring grid h-7 w-7 shrink-0 place-items-center rounded-control opacity-60 hover:opacity-100" aria-label="Dismiss">
              <X size={16} />
            </ToastPrimitive.Close>
          </ToastPrimitive.Root>
        );
      })}
      <ToastPrimitive.Viewport className="fixed inset-x-4 bottom-[calc(5rem+env(safe-area-inset-bottom))] z-[60] mx-auto flex max-w-sm flex-col gap-2 outline-none lg:bottom-6 lg:left-auto lg:right-6 lg:mx-0" />
    </ToastPrimitive.Provider>
  );
}
