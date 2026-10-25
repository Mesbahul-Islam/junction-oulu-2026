import { BadgeCheck, Check, CircleHelp, EyeOff, Hexagon, Lock, Plus, Search, Ticket } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { Badge, Button, Card, Dialog, DialogContent, Input, Meter, toast } from "@/components/ui";
import { Page, PageHeader, QueryBoundary } from "@/components/patterns";
import { cn } from "@/lib/utils";
import { useCancelPlan, useMyRewards, useRedeem, useSubscribe } from "../hooks";

const LABEL = { contributor: "Contributor", local_guide: "Local guide", trusted: "Trusted voice" };
// Your level is your best community standing (apps/trust/services.py POINTS and thresholds).
const EARN = [
  ["Reader note rated helpful", "+10"],
  ["Question or tip accepted by the newsroom", "+6"],
  ["...and it became a story", "+6"],
  ["Question other members asked too", "+3"],
  ["Like from another member (up to 5 per post)", "+1"],
  ["Photo approved by a moderator", "+1"],
  ["Note rating that matched the final verdict (up to 10)", "+1"],
  ["Reader note rated not helpful", "-4"],
  ["Post removed by a moderator", "-15"],
];

const off = (n) => (n >= 100 ? "Free" : `${n}% off`);
const day = (d) => new Date(d).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
const initials = (name) => name.split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();

function nextText(next) {
  if (!next) return null;
  if (next.editor) return "Trusted voice is given by a community editor, based on your record.";
  const parts = [
    next.points > 0 && `${next.points} more points`,
    next.verified > 0 && `${next.verified} more helpful note or accepted question`,
  ].filter(Boolean);
  return parts.length ? `${parts.join(" and ")} to ${LABEL[next.level]}` : null;
}

/** Level, points and what you get for them. */
function Hero({ stats, perks, plan, onPlan }) {
  const open = perks.filter((p) => p.percent > 0).map((p) => p.percent);
  const goal = stats.next?.points > 0 ? stats.points + stats.next.points : null;
  const range = open.length ? (Math.min(...open) === Math.max(...open) ? off(open[0]) : `${Math.min(...open)}% to ${off(Math.max(...open))}`) : null;
  return (
    <Card variant="float" className="flex flex-col items-center gap-2 bg-ink px-5 pb-6 pt-8 text-center text-on-ink">
      <span className="flex items-center gap-1.5 text-ui opacity-80">
        {stats.level === "trusted" && <BadgeCheck size={16} />}{stats.level_label}{stats.community && stats.level !== "reader" && ` in ${stats.community}`}{plan && " · Ad-free"}
      </span>
      <span className="flex items-center gap-2 text-hero tabular-nums">
        <Hexagon size={34} fill="currentColor" strokeWidth={0} />{stats.points}
      </span>
      <span className="text-ui opacity-80">
        {range ? `${range} at ${open.length} partners` : "Reach Contributor in any community to unlock partner discounts"}
      </span>
      {goal && (
        <div className="mt-3 w-full max-w-xs text-left">
          <Meter label={nextText(stats.next)} value={Math.min(stats.points, goal)} max={goal} display={`${stats.points}/${goal}`}
            className="[&>span:nth-child(-n+2)]:text-on-ink/80 [&_[role=meter]]:bg-on-ink/20 [&_[role=meter]>span]:bg-on-ink" />
        </div>
      )}
      {!goal && nextText(stats.next) && <span className="mt-1 max-w-xs text-meta opacity-70">{nextText(stats.next)}</span>}
      <Button variant="secondary" size="sm" className="mt-4 border-transparent bg-on-ink/15 text-on-ink hover:bg-on-ink/25" onClick={onPlan}>
        {plan ? (plan.cancelled_at ? `Ad-free until ${day(plan.renews_on)}` : "Ad-free plan") : "Go ad-free"}
      </Button>
    </Card>
  );
}

function Action({ icon: Icon, label, onClick, to }) {
  const cls = "focus-ring flex flex-col items-center gap-2 rounded-card py-1 text-meta text-ink";
  const tile = <span className="grid h-14 w-14 place-items-center rounded-card border border-line bg-surface"><Icon size={22} strokeWidth={1.8} /></span>;
  return to ? <Link to={to} className={cls}>{tile}{label}</Link> : <button type="button" onClick={onClick} className={cls}>{tile}{label}</button>;
}

// Logos whose emblem sits at the left of the wordmark: show the emblem instead of the middle letters.
const EMBLEM_LEFT = new Set(["prisma", "verkkokauppa", "powerpark"]);

/** Brand logo in a white circle. Wide wordmarks start at their emblem or first letters and run off the
 *  edge; square logos fill it. */
function Logo({ slug, name, className }) {
  const [failed, setFailed] = useState(false);
  const [wide, setWide] = useState(false);
  const fit = !wide ? "inset-0 h-full w-full object-cover"
    : EMBLEM_LEFT.has(slug) ? "left-[12%] top-1/2 h-[62%] w-auto max-w-none -translate-y-1/2"
      : "left-[14%] top-1/2 h-[36%] w-auto max-w-none -translate-y-1/2";
  return (
    <span className={cn("relative grid h-11 w-11 shrink-0 place-items-center overflow-hidden rounded-full border border-line bg-white", className)}>
      {failed ? <span className="text-meta font-semibold text-[#1a1a1a]">{initials(name)}</span> : (
        <img src={`/partners/${slug}.webp`} alt={name} onError={() => setFailed(true)}
          onLoad={(e) => setWide(e.currentTarget.naturalWidth > 1.5 * e.currentTarget.naturalHeight)}
          className={cn("absolute", fit)} />
      )}
    </span>
  );
}

/** One partner: what you get at every level and your code. */
function PartnerSheet({ perk, level, code, onClose }) {
  const redeem = useRedeem();
  const [got, setGot] = useState(null);
  const shown = got || code;
  if (!perk) return null;
  const get = () => redeem.mutate(perk.id, {
    onSuccess: setGot,
    onError: (e) => toast({ title: "No code", description: e.message, tone: "danger" }),
  });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent placement="sheet" title={perk.partner} description={`${perk.city} · ${perk.category}`}>
        <Logo slug={perk.slug} name={perk.partner} className="h-16 w-16" />
        <div className="flex flex-col gap-1">
          <span className="text-display">{perk.percent > 0 ? off(perk.percent) : "Locked"}</span>
          <span className="text-ui text-muted">{perk.title}</span>
        </div>
        <Card className="divide-y divide-line">
          {perk.ladder.map((l) => (
            <div key={l.level} className={cn("flex items-center gap-3 px-4 py-3", l.level === level && "bg-sunk")}>
              <span className="flex-1 text-ui">{l.label}</span>
              {l.level === level && <span className="text-caption text-muted">You</span>}
              <span className="w-20 text-right text-ui font-medium tabular-nums">{l.percent ? off(l.percent) : "–"}</span>
            </div>
          ))}
        </Card>
        {shown ? (
          <div className="flex flex-col gap-2">
            <div className="rounded-card border border-dashed border-line bg-sunk px-4 py-5 text-center">
              <span className="select-all font-mono text-headline tracking-[0.12em]">{shown.code}</span>
            </div>
            <p className="text-meta text-muted">{off(shown.percent)} {shown.title}. {perk.city === "Online" ? "Enter the code at checkout" : `Show the code at ${perk.partner}`}. Valid until {day(shown.valid_until)}.</p>
          </div>
        ) : perk.percent > 0 ? (
          <Button size="lg" block disabled={redeem.isPending || perk.sold_out} onClick={get}>
            {perk.sold_out ? "No codes left this month" : "Get code"}
          </Button>
        ) : (
          <Button size="lg" block disabled><Lock size={16} />Unlocks at {perk.min_level_label}</Button>
        )}
        {perk.terms && <p className="text-caption text-muted">{perk.terms} One code per month.</p>}
      </DialogContent>
    </Dialog>
  );
}

function EarnSheet({ open, onClose }) {
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent placement="sheet" title="Earn points" description="Points come from what others verified, in each community. Your best community sets your level.">
        <Card className="divide-y divide-line">
          {EARN.map(([what, pts]) => (
            <div key={what} className="flex items-center gap-3 px-4 py-3">
              <span className="flex-1 text-ui">{what}</span>
              <span className="text-ui font-medium tabular-nums">{pts}</span>
            </div>
          ))}
        </Card>
        <Card className="divide-y divide-line">
          <div className="flex gap-3 px-4 py-3"><span className="flex-1 text-ui">Contributor</span><span className="text-meta text-muted">15 points in one community</span></div>
          <div className="flex gap-3 px-4 py-3"><span className="flex-1 text-ui">Local guide</span><span className="text-right text-meta text-muted">50 points and 2 helpful notes or accepted questions</span></div>
          <div className="flex gap-3 px-4 py-3"><span className="flex-1 text-ui">Trusted voice</span><span className="text-meta text-muted">Approved by an editor</span></div>
        </Card>
        <Button asChild variant="secondary" block><Link to="/communities">Go to Community</Link></Button>
      </DialogContent>
    </Dialog>
  );
}

function CodesSheet({ open, codes, onClose }) {
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent placement="sheet" title="My codes">
        {codes.length ? (
          <Card className="divide-y divide-line">
            {codes.map((c) => (
              <div key={c.id} className="flex items-center gap-3 px-4 py-3">
                <Logo slug={c.slug} name={c.partner} />
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate text-ui font-medium">{c.partner}</span>
                  <span className="truncate text-meta text-muted">{off(c.percent)} · until {day(c.valid_until)}</span>
                </span>
                <span className="select-all font-mono text-meta">{c.code}</span>
              </div>
            ))}
          </Card>
        ) : <p className="text-ui text-muted">Codes you take from partners show here.</p>}
      </DialogContent>
    </Dialog>
  );
}

function PlanSheet({ open, plan, onClose }) {
  const [billing, setBilling] = useState("yearly");
  const subscribe = useSubscribe();
  const cancel = useCancelPlan();
  const options = [["monthly", "Monthly", "€1 a month"], ["yearly", "Yearly", "€10 a year, 2 months free"]];
  const fail = (e) => toast({ title: "Not changed", description: e.message, tone: "danger" });
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent placement="sheet" title="Ad-free" description="No ads anywhere in the app. Your level and partner discounts stay the same.">
        {plan && (
          <Card variant="sunk" className="flex flex-col gap-0.5 px-4 py-3">
            <span className="text-ui font-medium">{plan.price}</span>
            <span className="text-meta text-muted">{plan.cancelled_at ? `Cancelled. Ad-free until ${day(plan.renews_on)}.` : `Renews ${day(plan.renews_on)}.`}</span>
          </Card>
        )}
        {(!plan || plan.cancelled_at) && (
          <>
            <Card className="divide-y divide-line">
              {options.map(([value, label, price]) => (
                <button key={value} type="button" onClick={() => setBilling(value)}
                  className="focus-ring flex w-full items-center gap-3 px-4 py-3.5 text-left">
                  <span className="flex flex-1 flex-col">
                    <span className="text-ui font-medium">{label}</span>
                    <span className="text-meta text-muted">{price}</span>
                  </span>
                  <span className={cn("grid h-5 w-5 place-items-center rounded-full border", billing === value ? "border-ink bg-ink text-on-ink" : "border-line")}>
                    {billing === value && <Check size={12} strokeWidth={3} />}
                  </span>
                </button>
              ))}
            </Card>
            <Button size="lg" block disabled={subscribe.isPending}
              onClick={() => subscribe.mutate(billing, { onSuccess: () => { toast({ title: "You're ad-free", tone: "confirmed" }); onClose(); }, onError: fail })}>
              Subscribe
            </Button>
          </>
        )}
        {plan && !plan.cancelled_at && (
          <Button variant="secondary" block disabled={cancel.isPending} onClick={() => cancel.mutate(undefined, { onError: fail })}>Cancel plan</Button>
        )}
      </DialogContent>
    </Dialog>
  );
}

/** Rewards: your trust standing (apps/trust) as a level, partner discounts that grow with your level,
 *  and the ad-free plan. Discounts and codes only, no cash. */
export default function Rewards() {
  const query = useMyRewards();
  const [category, setCategory] = useState("All");
  const [search, setSearch] = useState("");
  const [sheet, setSheet] = useState(null); // "earn" | "codes" | "plan" | perk id

  return (
    <Page className="pb-10">
      <PageHeader back title="Rewards" actions={
        <Button asChild variant="ghost" size="icon" aria-label="Help"><Link to="/help"><CircleHelp size={20} /></Link></Button>} />
      <QueryBoundary query={query} isEmpty={() => false}>
        {(data) => <Body data={data} category={category} setCategory={setCategory} search={search} setSearch={setSearch} sheet={sheet} setSheet={setSheet} />}
      </QueryBoundary>
    </Page>
  );
}

function Body({ data, category, setCategory, search, setSearch, sheet, setSheet }) {
  const categories = useMemo(() => ["All", ...new Set(data.perks.map((p) => p.category))], [data.perks]);
  const codeNow = Object.fromEntries(data.codes.filter((c) => c.month === data.month).map((c) => [c.perk, c]));
  const q = search.trim().toLowerCase();
  const list = data.perks
    .filter((p) => (category === "All" || p.category === category) && (!q || `${p.partner} ${p.title} ${p.category}`.toLowerCase().includes(q)))
    .sort((a, b) => b.percent - a.percent || a.partner.localeCompare(b.partner));
  const perk = typeof sheet === "number" ? data.perks.find((p) => p.id === sheet) : null;

  return (
    <div className="flex flex-col gap-7 pt-2">
      <Hero stats={data.stats} perks={data.perks} plan={data.plan} onPlan={() => setSheet("plan")} />

      <div className="grid grid-cols-4">
        <Action icon={Plus} label="Earn" onClick={() => setSheet("earn")} />
        <Action icon={Ticket} label="My codes" onClick={() => setSheet("codes")} />
        <Action icon={EyeOff} label="Ad-free" onClick={() => setSheet("plan")} />
        <Action icon={CircleHelp} label="Help" to="/help" />
      </div>

      <section className="flex flex-col gap-3">
        <h2 className="text-headline">Partners</h2>
        <div className="relative">
          <Search size={17} className="pointer-events-none absolute start-3 top-1/2 -translate-y-1/2 text-muted" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search partners" className="ps-9" aria-label="Search partners" />
        </div>
        <div className="-mx-4 flex gap-1 overflow-x-auto px-4 [scrollbar-width:none] sm:mx-0 sm:px-0">
          {categories.map((c) => (
            <button key={c} type="button" onClick={() => setCategory(c)}
              className={cn("focus-ring h-9 shrink-0 rounded-control px-3 text-meta transition-colors",
                category === c ? "bg-ink font-medium text-on-ink" : "text-muted hover:bg-sunk hover:text-ink")}>
              {c}
            </button>
          ))}
        </div>
        <Card className="divide-y divide-line">
          {list.map((p) => (
            <button key={p.id} type="button" onClick={() => setSheet(p.id)}
              className="focus-ring flex w-full items-center gap-3 px-4 py-3.5 text-left hover:bg-sunk/60">
              <Logo slug={p.slug} name={p.partner} />
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate text-ui font-medium">{p.partner}</span>
                <span className="truncate text-meta text-muted">{p.title}</span>
              </span>
              {codeNow[p.id] ? (
                <Badge tone="confirmed"><Ticket size={12} />Code</Badge>
              ) : p.percent > 0 ? (
                <Badge className="bg-sunk px-3 text-meta text-ink">{off(p.percent)}</Badge>
              ) : (
                <Badge appearance="outline"><Lock size={11} />{p.min_level_label}</Badge>
              )}
            </button>
          ))}
          {!list.length && <p className="px-4 py-6 text-center text-ui text-muted">No partners match.</p>}
        </Card>
      </section>

      <PartnerSheet key={perk?.id} perk={perk} level={data.stats.level} code={perk && codeNow[perk.id]} onClose={() => setSheet(null)} />
      <EarnSheet open={sheet === "earn"} onClose={() => setSheet(null)} />
      <CodesSheet open={sheet === "codes"} codes={data.codes} onClose={() => setSheet(null)} />
      <PlanSheet open={sheet === "plan"} plan={data.plan} onClose={() => setSheet(null)} />
    </div>
  );
}
