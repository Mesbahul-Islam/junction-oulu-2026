import { ChevronLeft } from "lucide-react";

import { Button, Stepper } from "@/components/ui";
import { cn } from "@/lib/utils";

export function OnboardingShell({
  step,
  total,
  title,
  subtitle,
  onBack,
  children,
  cta,
  className,
}) {
  const backHandler = () => {
    if (typeof onBack === "function") {
      onBack();
      return;
    }
  };

  return (
    <main className={cn("flex min-h-dvh flex-col bg-paper font-sans text-ink", className)}>
      <header className="sticky top-0 z-10 bg-paper/90 backdrop-blur-md">
        <div className="mx-auto flex h-16 w-full max-w-2xl items-center gap-3 px-4 pt-[env(safe-area-inset-top)] sm:px-6 lg:h-[72px] lg:px-8">
          <Button
            variant="ghost"
            size="icon"
            aria-label="Back"
            onClick={backHandler}
            className="-ms-2"
            disabled={step === 0 && typeof onBack !== "function"}
          >
            <ChevronLeft size={22} className="rtl:rotate-180" />
          </Button>
          <Stepper total={total} current={step} className="flex-1" />
          <span className="w-10 text-center text-caption tabular-nums text-muted">
            {step + 1}/{total}
          </span>
        </div>
      </header>

      <section
        key={step}
        className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-8 px-4 pb-36 pt-6 duration-300 ease-kajo animate-in fade-in-0 slide-in-from-bottom-2 sm:px-6 sm:pt-10 lg:px-8 lg:pt-14"
      >
        <div className="flex flex-col gap-3">
          <h1 className="text-display text-balance sm:text-[34px] sm:leading-[1.04] sm:tracking-[-0.028em] lg:text-hero">
            {title}
          </h1>
          {subtitle && <p className="max-w-[60ch] text-ui text-muted">{subtitle}</p>}
        </div>
        {children}
      </section>

      <footer className="fixed inset-x-0 bottom-0 z-10">
        <div className="mx-auto w-full max-w-2xl px-4 pb-[max(1.25rem,env(safe-area-inset-bottom))] pt-4 sm:px-6 lg:px-8">
          <div className="rounded-card bg-paper/95 p-2 shadow-[0_-1px_0_hsl(var(--line-hsl)),0_1px_2px_hsl(var(--ink-hsl)/0.02)] backdrop-blur-md">
            <Button size="lg" block disabled={cta?.disabled} onClick={cta?.onClick}>
              {cta?.label}
            </Button>
          </div>
        </div>
      </footer>
    </main>
  );
}
