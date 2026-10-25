import { ChevronLeft, Languages, MapPin, Sparkles, UsersRound } from "lucide-react";
import { useEffect, useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";

import { Badge, Button, Field, Input, RadioCards, Skeleton, Spinner, Stepper, ToggleChips } from "@/components/ui";
import { OnboardingShell } from "@/components/patterns";
import { getInterests, resolveCode, saveOnboarding } from "@/features/account/api";
import { LocationStep } from "@/features/account/components/LocationStep";
import { getRecommendedCommunities, joinCommunity } from "@/features/communities/api";
import { useAuth } from "@/features/auth/AuthProvider";
import { LANGUAGES, SAMI, SITUATIONS } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const STEPS = ["language", "location", "topics", "situation", "communities"];
const PRESELECT_SCORE = 3;

const COPY = {
  language: {
    title: "Choose your reading language",
    subtitle: "Every story is translated into this language. You'll always see the Finnish original with one tap.",
  },
  location: {
    title: "Where do you live?",
    subtitle: "We show you news from your own municipality, so we need your location for local coverage.",
  },
  topics: {
    title: "What matters to you in {town}?",
    subtitle: "Pick what affects your life. We'll put them first in For You.",
  },
  situation: {
    title: "Tell us your situation",
    subtitle: "This helps explain why each story matters for you — not just what happened.",
  },
  communities: {
    title: "Find your people",
    subtitle: "Communities are where readers help each other in their own language. Pick what feels right.",
  },
};

const STEP_ICONS = [Languages, MapPin, Sparkles, UsersRound, UsersRound];

export default function Onboarding() {
  const { me, loading, refresh } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [step, setStep] = useState(0);
  const [interests, setInterests] = useState(null);
  const [form, setForm] = useState(null);
  const [code, setCode] = useState(params.get("code") || "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const [picked, setPicked] = useState([]);
  const [town, setTown] = useState(null);

  useEffect(() => {
    getInterests().then((data) => setInterests(Array.isArray(data) ? data : data.results || []));
  }, []);

  useEffect(() => {
    if (!me || form) return;
    setForm({
      preferred_language: me.preferred_language || "uk",
      interests: me.profile?.interests || [],
      reader_situation: me.reader_situation || "newcomer",
      arrival_date: me.arrival_date || "",
    });
  }, [me, form]);

  useEffect(() => {
    if (!code || !form) return;
    resolveCode(code)
      .then((link) => {
        const arrival = new Date(Date.now() - (link.default_arrival_offset_days || 0) * 86400000).toISOString().slice(0, 10);
        setForm((f) => ({ ...f, preferred_language: link.language || f.preferred_language, arrival_date: f.arrival_date || arrival }));
      })
      .catch(() => setCode(""));
  }, [code, form]);

  if (loading || (me && !form)) return <div className="grid min-h-dvh place-items-center bg-paper"><Spinner /></div>;
  if (!me) return <Navigate to={`/welcome?code=${encodeURIComponent(code)}`} replace />;

  const set = (patch) => setForm((f) => ({ ...f, ...patch }));

  const run = async (work) => {
    setBusy(true);
    setError("");
    try {
      await work();
    } catch (err) {
      setError(Object.values(err.data || {}).flat()[0] || err.message);
    } finally {
      setBusy(false);
    }
  };

  const savePreferences = () =>
    run(async () => {
      await saveOnboarding({
        ...form,
        arrival_date: form.arrival_date || null,
        ...(code ? { onboarding_code: code } : {}),
        ...(town ? { municipality_code: town.code } : {}),
      });
      await refresh();
      const list = await getRecommendedCommunities();
      setSuggestions(list);
      setPicked(list.filter((c) => c.score >= PRESELECT_SCORE).map((c) => c.slug));
      setStep(STEPS.indexOf("communities"));
    });

  const finish = () =>
    run(async () => {
      for (const slug of picked) await joinCommunity(slug);
      await refresh();
      navigate("/", { replace: true });
    });

  const name = STEPS[step];
  const copy = { ...COPY[name], title: COPY[name].title.replace("{town}", town?.name || "your area") };
  const StepIcon = STEP_ICONS[step];

  const cta = {
    language: { label: "Continue", onClick: () => setStep(1) },
    location: { label: town ? "Continue" : "Skip for now", onClick: () => setStep(2) },
    topics: { label: "Continue", onClick: () => setStep(3), disabled: !(form.interests && form.interests.length) },
    situation: { label: busy ? "Saving…" : "Continue", onClick: savePreferences, disabled: busy },
    communities: {
      label: busy ? "Joining…" : picked.length ? `Join ${picked.length} ${picked.length === 1 ? "community" : "communities"} & start reading` : "Skip and start reading",
      onClick: finish,
      disabled: busy,
    },
  }[name];

  const goBack = () => {
    if (step === 0) {
      navigate("/welcome", { replace: true });
      return;
    }
    setStep(step - 1);
  };

  return (
    <OnboardingShell
      step={step}
      total={STEPS.length}
      title={copy.title}
      subtitle={copy.subtitle}
      onBack={goBack}
      cta={cta}
    >
      <div className="flex items-center gap-2 text-caption text-muted">
        <StepIcon size={16} />
        <span className="uppercase tracking-[0.16em]">Step {step + 1} of {STEPS.length}</span>
      </div>

      {error && <p role="alert" className="rounded-control border border-danger/40 bg-danger-weak px-3.5 py-2.5 text-meta text-danger">{error}</p>}

      {name === "language" && (
        <div className="flex flex-col gap-4">
          <RadioCards
            aria-label="Language"
            value={form.preferred_language}
            onValueChange={(v) => v && set({ preferred_language: v })}
            options={LANGUAGES.map((l) => ({ value: l.code, l }))}
            columns="grid-cols-1 sm:grid-cols-2 lg:grid-cols-3"
            renderOption={({ l }) => (
              <span className="flex flex-col gap-1">
                <span className="text-title" dir="auto" lang={l.code}>{l.name}</span>
                <span className="text-meta text-muted">{l.english}</span>
              </span>
            )}
          />
          {SAMI.has(form.preferred_language) && (
            <div className="flex gap-3 rounded-card border border-line bg-sunk/60 p-4">
              <Sparkles size={18} className="mt-0.5 shrink-0 text-newsroom" />
              <p className="text-ui text-muted">
                Sámi stories are translated by people, not by machine, so there are fewer of them. Until a translation is ready, you'll see the Finnish original.
              </p>
            </div>
          )}
        </div>
      )}

      {name === "location" && <LocationStep town={town} onTown={setTown} />}

      {name === "topics" && (
        interests === null ? (
          <div className="flex flex-wrap gap-2">
            {[112, 96, 124, 88, 108, 84, 132].map((w, i) => (
              <Skeleton key={i} className="h-11 rounded-pill" style={{ width: w }} />
            ))}
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <ToggleChips
              aria-label="Topics"
              value={form.interests}
              onValueChange={(v) => set({ interests: v })}
              options={interests.map((i) => ({ value: i.slug, label: i.name }))}
            />
            <p className="text-meta text-muted" aria-live="polite">
              {form.interests && form.interests.length ? `${form.interests.length} selected` : "Pick at least one to continue"}
            </p>
          </div>
        )
      )}

      {name === "situation" && (
        <div className="flex flex-col gap-6">
          <RadioCards
            aria-label="Your situation"
            value={form.reader_situation}
            onValueChange={(v) => v && set({ reader_situation: v })}
            options={SITUATIONS.map((s) => ({ value: s.value, label: s.label }))}
            columns="grid-cols-1 sm:grid-cols-2"
          />
          <Field label="When did you arrive in Finland?" htmlFor="arrival" hint="Optional. Helps us flag deadlines that matter in your first months.">
            <Input id="arrival" type="date" value={form.arrival_date || ""} onChange={(e) => set({ arrival_date: e.target.value })} />
          </Field>
        </div>
      )}

      {name === "communities" && (
        <div className="flex flex-col gap-4">
          {suggestions.length === 0 ? (
            <div className="rounded-card border border-line bg-sunk/40 p-6">
              <p className="text-ui text-muted">You're already in every community that fits you. You can find more later in Community.</p>
            </div>
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-2 text-meta text-muted">
                <Badge tone="confirmed">Recommended for you</Badge>
                <span>{picked.length} selected</span>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                {suggestions.map((c) => {
                  const active = picked.includes(c.slug);
                  return (
                    <button
                      key={c.slug}
                      type="button"
                      onClick={() => setPicked((prev) => (prev.includes(c.slug) ? prev.filter((s) => s !== c.slug) : [...prev, c.slug]))}
                      className={cn(
                        "focus-ring flex flex-col gap-3 rounded-card border p-5 text-left transition-all duration-150 ease-kajo",
                        active ? "border-ink bg-surface shadow-[inset_0_0_0_1px_hsl(var(--ink-hsl))]" : "border-line bg-surface hover:border-ink/30 hover:bg-ink/[0.01]",
                      )}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex flex-col gap-1">
                          <span className="text-title">{c.name}</span>
                          {c.description && <span className="text-ui text-muted">{c.description}</span>}
                        </div>
                        <span
                          className={cn(
                            "mt-1 h-2.5 w-2.5 rounded-full",
                            active ? "bg-ink" : "bg-line",
                          )}
                        />
                      </div>
                      <div className="flex flex-wrap items-center gap-1.5">
                        {c.reasons?.map((r) => (
                          <Badge key={r} tone="newsroom">{r}</Badge>
                        ))}
                        <span className="text-caption text-muted">
                          {c.member_count} {c.member_count === 1 ? "member" : "members"}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </>
          )}
        </div>
      )}
    </OnboardingShell>
  );
}
