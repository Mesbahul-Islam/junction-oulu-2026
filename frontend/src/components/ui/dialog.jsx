import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";

import { cn } from "@/lib/utils";

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;

const PLACEMENT = {
  // A focused decision: centred card on every screen.
  center:
    "left-1/2 top-1/2 w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-sheet p-6 " +
    "data-[state=open]:zoom-in-95 data-[state=closed]:zoom-out-95",
  // Secondary content (comments, notes): bottom sheet on phones, side panel on desktop.
  sheet:
    "inset-x-0 bottom-0 max-h-[88dvh] rounded-t-sheet px-5 pb-[max(1.5rem,env(safe-area-inset-bottom))] pt-3 " +
    "data-[state=open]:slide-in-from-bottom data-[state=closed]:slide-out-to-bottom " +
    "md:inset-y-0 md:left-auto md:right-0 md:max-h-none md:w-[440px] md:rounded-none md:rounded-l-sheet md:p-7 " +
    "md:data-[state=open]:slide-in-from-right md:data-[state=closed]:slide-out-to-right",
};

/** Dialog body. `placement`: "center" (default) or "sheet". Always give it a title (a11y). */
export function DialogContent({ placement = "center", title, description, children, className, hideClose }) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-ink/35 backdrop-blur-[2px] data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
      <DialogPrimitive.Content
        className={cn(
          "fixed z-50 flex flex-col gap-4 overflow-y-auto bg-surface font-sans text-ink shadow-float outline-none duration-300 ease-kajo",
          "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
          PLACEMENT[placement],
          className,
        )}
      >
        {placement === "sheet" && <span aria-hidden="true" className="mx-auto h-1 w-10 shrink-0 rounded-pill bg-line md:hidden" />}
        <div className="flex items-start gap-4">
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <DialogPrimitive.Title className="text-headline">{title}</DialogPrimitive.Title>
            {description && <DialogPrimitive.Description className="text-ui text-muted">{description}</DialogPrimitive.Description>}
          </div>
          {!hideClose && (
            <DialogPrimitive.Close className="focus-ring -mr-2 -mt-1 grid h-9 w-9 shrink-0 place-items-center rounded-control text-muted hover:bg-sunk hover:text-ink" aria-label="Close">
              <X size={18} />
            </DialogPrimitive.Close>
          )}
        </div>
        {children}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}
