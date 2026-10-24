import { Bookmark, Flag, MessageSquareText, Search, Share2, Sparkles, ThumbsUp } from "lucide-react";
import { useState } from "react";

import {
  Avatar, Badge, Button, Card, Dialog, DialogClose, DialogContent, DialogTrigger, Field, Input, Meter, RadioCards,
  Skeleton, Stepper, Switch, Tabs, TabsContent, TabsList, TabsTrigger, Textarea, ToggleCards, ToggleChips, toast,
} from "@/components/ui";
import {
  EmptyState, ErrorState, LangStatus, ListSkeleton, NeedTag, Page, Provenance, StoryCard, TrustBlock, Wordmark,
} from "@/components/patterns";
import { cn } from "@/lib/utils";

/* Sample data in the API's own shape, so this page doubles as a contract for the patterns. */
const now = new Date(Date.now() - 2 * 3600e3).toISOString();
const STORIES = [
  {
    id: 1, headline: "Kela changes how housing allowance is paid from January",
    summary: "Payments move to the first working day of the month. If you rent, check that your landlord's details are up to date.",
    language: "uk", requested_language: "uk", in_your_language: true, ai_disclosure: { machine_translated: true },
    reader_needs: ["usefulness"], published_at: now,
  },
  {
    id: 2, headline: "Oulu's winter bus timetable starts on Monday",
    summary: "Lines 3 and 8 run less often in the evenings; the night bus to Linnanmaa returns.",
    language: "fi", requested_language: "uk", in_your_language: false, reader_needs: ["information"], published_at: now,
  },
  {
    id: 3, headline: "Sámi Parliament opens applications for language nest staff",
    summary: "Inari and Skolt Sámi speakers are especially sought.",
    language: "se", requested_language: "se", in_your_language: true, ai_disclosure: { machine_translated: false },
    reader_needs: ["community"], published_at: now,
  },
  {
    id: 4, headline: "Where to get winter tyres changed before the first snow",
    summary: "Readers in the newcomers group asked; we checked prices at six garages.",
    language: "uk", requested_language: "uk", in_your_language: true, ai_disclosure: { machine_translated: true },
    community: "newcomers-oulu", reader_needs: ["usefulness"], published_at: now,
  },
];

const TONES = [
  { tone: "newsroom", dot: "bg-newsroom", name: "Newsroom", hex: "#1B4BD0", meaning: "An editor reviewed this. It's in your language." },
  { tone: "community", dot: "bg-community", name: "Community", hex: "#A45404", meaning: "A member's own words, not checked by editors." },
  { tone: "confirmed", dot: "bg-confirmed", name: "Confirmed", hex: "#16744D", meaning: "People confirmed it: a note is shown, a vote got it covered." },
  { tone: "danger", dot: "bg-danger", name: "Correction", hex: "#BF3722", meaning: "Something was wrong, or the stakes are high." },
];
const NEUTRALS = [
  ["bg-paper", "Snow", "Page ground"], ["bg-surface", "Surface", "Cards, sheets"], ["bg-sunk", "Sunk", "Wells, tracks"],
  ["bg-line", "Line", "Hairlines"], ["bg-muted", "Muted", "Secondary text"], ["bg-ink", "Polar night", "Text, primary actions"],
];
const TYPE = [
  ["hero", "text-[34px] leading-[1.05] font-semibold tracking-[-0.028em] sm:text-hero", "Local news, in your language."],
  ["display", "text-display", "What this means for you"], ["headline", "text-headline", "Kela changes housing allowance"],
  ["title", "text-title", "Reviewed by an editor"], ["lead", "text-lead", "Every story is explained for where you are in life."],
  ["body", "text-body", "Payments move to the first working day of the month. If you rent, check your landlord's details."],
  ["ui", "text-ui", "Buttons, inputs and lists"], ["meta", "text-meta", "Checked by a person on 24 Oct"], ["caption", "text-caption", "2 hours ago"],
];

function Section({ title, intro, children }) {
  return (
    <section className="grid gap-6 border-t border-line py-12 lg:grid-cols-[220px_minmax(0,1fr)] lg:gap-12">
      <div className="flex flex-col gap-2">
        <h2 className="text-headline">{title}</h2>
        {intro && <p className="text-meta text-muted">{intro}</p>}
      </div>
      <div className="flex min-w-0 flex-col gap-6">{children}</div>
    </section>
  );
}

function ThemeToggle() {
  const [theme, setTheme] = useState(document.documentElement.dataset.theme || "system");
  const pick = (t) => {
    setTheme(t);
    if (t === "system") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = t;
  };
  return (
    <div role="radiogroup" aria-label="Theme" className="inline-flex rounded-control border border-line bg-surface p-0.5">
      {["system", "light", "dark"].map((t) => (
        <button key={t} role="radio" aria-checked={theme === t} onClick={() => pick(t)}
          className={cn("focus-ring h-8 rounded-[9px] px-3 text-meta capitalize", theme === t ? "bg-ink text-on-ink" : "text-muted hover:text-ink")}>
          {t}
        </button>
      ))}
    </div>
  );
}

export default function DesignSystem() {
  const [lang, setLang] = useState("uk");
  const [topics, setTopics] = useState(["housing", "work"]);
  const [fantasy, setFantasy] = useState(false);

  return (
    <div className="min-h-dvh bg-paper font-sans text-ink">
      <Page wide>
        <header className="flex items-center justify-between gap-4 py-6">
          <Wordmark />
          <ThemeToggle />
        </header>

        <div className="flex max-w-3xl flex-col gap-5 pb-14 pt-10 lg:pt-16">
          <h1 className="text-[34px] font-semibold leading-[1.04] tracking-[-0.028em] sm:text-hero">
            Colour tells you who is speaking.
          </h1>
          <p className="max-w-[58ch] text-lead text-muted">
            Kajo is the design system for Oulu News. The interface is monochrome, ink on snow. Colour appears only to say who
            stands behind a piece of content: the newsroom, a community member, people who confirmed it, or a correction.
            A reader learns that once and can rely on it on every screen.
          </p>
        </div>

        <Section title="Provenance" intro="The only four colours in the product. Each one is a promise about the source.">
          <div className="grid gap-3 sm:grid-cols-2">
            {TONES.map((t) => (
              <Card key={t.tone} className="flex flex-col gap-4 p-5">
                <div className="flex items-center gap-3">
                  <span className={cn("h-10 w-10 rounded-full", t.dot)} />
                  <div className="flex flex-col">
                    <span className="text-title">{t.name}</span>
                    <span className="text-caption tabular-nums text-muted">{t.hex}</span>
                  </div>
                </div>
                <p className="text-ui text-muted">{t.meaning}</p>
                <div className="flex flex-wrap gap-2">
                  <Badge tone={t.tone} appearance="solid">Solid</Badge>
                  <Badge tone={t.tone}>Soft</Badge>
                  <Badge tone={t.tone} appearance="outline">Outline</Badge>
                </div>
              </Card>
            ))}
          </div>
          <div className="grid grid-cols-3 gap-3 sm:grid-cols-6">
            {NEUTRALS.map(([v, name, use]) => (
              <div key={v} className="flex flex-col gap-2">
                <span className={cn("h-14 rounded-control border border-line", v)} />
                <span className="text-meta font-medium">{name}</span>
                <span className="-mt-1.5 text-caption text-muted">{use}</span>
              </div>
            ))}
          </div>
        </Section>

        <Section title="Type" intro="IBM Plex Sans with its Arabic cut: one voice in every script our readers use, Sámi diacritics included.">
          <div className="flex flex-col divide-y divide-line">
            {TYPE.map(([size, cls, sample]) => (
              <div key={size} className="grid grid-cols-[72px_minmax(0,1fr)] items-baseline gap-4 py-3">
                <span className="text-caption text-muted">{size}</span>
                <span className={cls}>{sample}</span>
              </div>
            ))}
          </div>
          <Card variant="sunk" className="grid gap-3 p-5 sm:grid-cols-2">
            <p className="text-title" lang="uk">Kela змінює виплату житлової допомоги з січня</p>
            <p className="text-title" lang="ar" dir="rtl">كيلا تغيّر طريقة دفع إعانة السكن ابتداءً من يناير</p>
            {/* Glyph coverage only: we don't put unchecked sentences in Sámi on screen. */}
            <p className="text-title" lang="se" aria-label="Northern Sámi letters">Á á Č č Đ đ Ŋ ŋ Š š Ŧ ŧ Ž ž</p>
            <p className="text-title" lang="sms" aria-label="Skolt Sámi letters">Ǩ ǩ Ǧ ǧ Õ õ Ʒ ʒ Ǯ ǯ Å å ʹ</p>
          </Card>
        </Section>

        <Section title="Trust devices" intro="How a story shows its source, its language and what it means for the reader. These lead on the story page; they never hide in a footer.">
          <div className="flex flex-wrap gap-2">
            <LangStatus state="yours" language="uk" />
            <LangStatus state="human" language="se" />
            <LangStatus state="fallback" language="fi" requested="uk" />
            <LangStatus state="original" language="fi" />
          </div>
          <div className="flex flex-wrap gap-x-5 gap-y-2">
            {["information", "understanding", "usefulness", "emotion", "break", "community"].map((n) => <NeedTag key={n} need={n} />)}
          </div>
          <div className="grid gap-5 sm:grid-cols-3">
            <Provenance kind="newsroom" reviewer="Aino Korhonen" date={now} machineTranslated />
            <Provenance kind="community" author="@olena_k" community="Newcomers in Oulu" />
            <Provenance kind="correction" date={now} />
          </div>
          <div className="flex flex-col gap-3">
            <TrustBlock tone="newsroom" icon={Sparkles} title="What this means for you">
              <p>You just moved here, so your first payment may come a few weeks after you apply. If rent is due before that, ask Kela for an advance.</p>
            </TrustBlock>
            <TrustBlock tone="confirmed" icon={MessageSquareText} title="Community note">
              <p>The Kela office on Isokatu takes walk-ins only on Tuesdays. Booking online is faster.</p>
            </TrustBlock>
            <TrustBlock tone="danger" icon={Flag} title="Correction">
              <p>An earlier version said payments move in December. The change starts in January.</p>
            </TrustBlock>
            <TrustBlock tone="neutral" title="Not yet in Ukrainian" action={<Button variant="link" size="sm">Get notified when it's ready</Button>}>
              <p>You're reading the Finnish original. A translation is waiting for an editor's review.</p>
            </TrustBlock>
          </div>
          <Card className="flex flex-col gap-4 p-5">
            <h3 className="text-title">Why you're seeing this</h3>
            <Meter label="Affects you" value={0.78} tone="newsroom" />
            <Meter label="Your interests" value={0.54} tone="newsroom" />
            <Meter label="Action needed" value={0.9} tone="newsroom" />
          </Card>
        </Section>

        <Section title="Stories" intro="A reading list, not a card grid: hairlines between stories, the lead story given room.">
          <Tabs defaultValue="you">
            <TabsList>
              <TabsTrigger value="you">For you</TabsTrigger>
              <TabsTrigger value="community">From your community</TabsTrigger>
            </TabsList>
            <TabsContent value="you" className="max-w-read">
              <StoryCard card={STORIES[0]} variant="lead" onOpen={() => {}} />
              <div className="divide-y divide-line border-t border-line">
                {STORIES.slice(1).map((s) => <StoryCard key={s.id} card={s} onOpen={() => {}} />)}
              </div>
            </TabsContent>
            <TabsContent value="community" className="max-w-read py-5">
              <Card className="flex flex-col gap-4 p-5">
                <Provenance kind="community" author="@olena_k" community="Newcomers in Oulu" />
                <p className="text-body" dir="auto">Does anyone know if the Tuira health station has Ukrainian-speaking nurses? Need an appointment for my son.</p>
                <div className="flex items-center gap-1 text-muted">
                  <Button variant="ghost" size="sm"><ThumbsUp size={16} />12</Button>
                  <Button variant="ghost" size="sm"><MessageSquareText size={16} />4 replies</Button>
                  <Button variant="ghost" size="sm" className="ms-auto">Ask the newsroom to check</Button>
                </div>
              </Card>
            </TabsContent>
          </Tabs>
        </Section>

        <Section title="Actions" intro="Primary actions are ink. One primary per view; everything else steps down.">
          <div className="flex flex-wrap items-center gap-3">
            <Button>Join and start reading</Button>
            <Button variant="secondary">Show the Finnish original</Button>
            <Button variant="ghost">Skip for now</Button>
            <Button variant="link">Read how we check stories</Button>
            <Button variant="danger">Report as wrong</Button>
            <Button disabled>Sending…</Button>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm">Small</Button>
            <Button size="lg">Large</Button>
            <Button variant="secondary" size="icon" aria-label="Save"><Bookmark size={18} /></Button>
            <Button variant="ghost" size="icon" aria-label="Share"><Share2 size={18} /></Button>
            <Button variant="ghost" size="icon-sm" aria-label="Search"><Search size={16} /></Button>
          </div>
        </Section>

        <Section title="Input" intro="Large, calm controls. Selection and focus are ink: they belong to the reader, not to a source.">
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Email" htmlFor="ds-email" hint="We never show it to other readers.">
              <Input id="ds-email" placeholder="you@example.com" />
            </Field>
            <Field label="Username" htmlFor="ds-user" error="Pick 3 to 30 letters, digits, _ or .">
              <Input id="ds-user" defaultValue="o" aria-invalid="true" />
            </Field>
          </div>
          <Field label="Your question for the newsroom" htmlFor="ds-q" hint="An editor reads every question. Nothing is published without a person.">
            <Textarea id="ds-q" placeholder="What should we find out?" />
          </Field>
          <label className="flex items-center justify-between gap-4 rounded-card border border-line bg-surface p-4">
            <span className="flex flex-col">
              <span className="text-title">Fantasy Liiga</span>
              <span className="text-meta text-muted">Show the hockey game in your menu.</span>
            </span>
            <Switch checked={fantasy} onCheckedChange={setFantasy} />
          </label>
          <RadioCards
            value={lang}
            onValueChange={(v) => v && setLang(v)}
            columns="grid-cols-1 sm:grid-cols-3"
            options={[
              { value: "uk", name: "Українська", en: "Ukrainian" },
              { value: "ar", name: "العربية", en: "Arabic" },
              { value: "se", name: "Davvisámegiella", en: "Northern Sámi" },
            ]}
            renderOption={(o) => (
              <span className="flex flex-col"><span className="text-title" dir="auto">{o.name}</span><span className="text-meta text-muted">{o.en}</span></span>
            )}
          />
          <ToggleCards
            value={topics}
            onValueChange={setTopics}
            columns="grid-cols-2 sm:grid-cols-4"
            options={[{ value: "housing", label: "Housing" }, { value: "work", label: "Work" }, { value: "health", label: "Health" }, { value: "transport", label: "Transport" }]}
          />
          <ToggleChips
            value={topics}
            onValueChange={setTopics}
            options={[{ value: "housing", label: "Housing" }, { value: "work", label: "Work" }, { value: "health", label: "Health" }, { value: "transport", label: "Transport" }, { value: "events", label: "Events" }]}
          />
          <Stepper total={4} current={1} className="max-w-xs" />
        </Section>

        <Section title="Overlays" intro="Dialogs for decisions, sheets for side content, toasts for confirmation. They replace every browser alert.">
          <div className="flex flex-wrap gap-3">
            <Dialog>
              <DialogTrigger asChild><Button variant="secondary"><Flag size={16} />Report a story</Button></DialogTrigger>
              <DialogContent title="What's wrong with this story?" description="An editor checks every report. The story is paused for readers until then.">
                <Textarea placeholder="For example: the office hours changed last week." />
                <div className="flex justify-end gap-2">
                  <DialogClose asChild><Button variant="ghost">Cancel</Button></DialogClose>
                  <DialogClose asChild>
                    <Button onClick={() => toast({ title: "Report sent", description: "An editor will check it today.", tone: "confirmed" })}>Send report</Button>
                  </DialogClose>
                </div>
              </DialogContent>
            </Dialog>
            <Dialog>
              <DialogTrigger asChild><Button variant="secondary"><MessageSquareText size={16} />Open replies</Button></DialogTrigger>
              <DialogContent placement="sheet" title="4 replies" description="Members' words. Not checked by editors.">
                {["olena_k", "mika.t", "sara_oulu"].map((u) => (
                  <div key={u} className="flex gap-3 border-t border-line pt-4">
                    <Avatar name={u} community />
                    <div className="flex flex-col gap-1">
                      <span className="text-meta font-medium">@{u}</span>
                      <p className="text-ui">Yes, ask for Nurse Halyna on Tuesdays. Booking works by phone too.</p>
                    </div>
                  </div>
                ))}
              </DialogContent>
            </Dialog>
            <Button variant="ghost" onClick={() => toast({ title: "Vote counted", description: "The newsroom decides at 15:00.", tone: "confirmed" })}>Show a toast</Button>
            <Button variant="ghost" onClick={() => toast({ title: "Couldn't send your vote", description: "You're offline. We'll try again when you reconnect.", tone: "danger" })}>Error toast</Button>
          </div>
        </Section>

        <Section title="States" intro="Every view that loads data has all three. Empty states invite; errors say what to do.">
          <div className="grid gap-4 lg:grid-cols-3">
            <Card className="px-5"><ListSkeleton rows={2} /></Card>
            <Card><EmptyState icon={Bookmark} title="No saved stories" action={<Button size="sm" variant="secondary">Browse today's news</Button>}>Tap the bookmark on any story to read it later.</EmptyState></Card>
            <Card><ErrorState error={{ message: "The newsroom didn't answer" }} onRetry={() => {}} /></Card>
          </div>
          <div className="flex items-center gap-3">
            <Avatar name="Aino Korhonen" size="lg" />
            <Avatar name="olena_k" community />
            <Avatar name="mika" size="sm" />
            <Skeleton className="h-4 w-40" />
          </div>
        </Section>

        <footer className="border-t border-line py-10 text-meta text-muted">Kajo: the faint light of the polar night.</footer>
      </Page>
    </div>
  );
}
