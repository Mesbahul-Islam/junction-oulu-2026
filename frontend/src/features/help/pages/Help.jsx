import { Minus, Plus, Search } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Button, Input } from "@/components/ui";
import { Page, PageHeader } from "@/components/patterns";
import { cn } from "@/lib/utils";

const FAQS = [
  {
    topic: "Reading",
    q: "Can I trust the news here?",
    a: "Stories from Kaleva's newsroom are written with AI help and checked by an editor before they are published. Each one says \"Reviewed by\" and the editor's name. Posts from members say \"A member's words. Not checked by editors.\" so you always know which is which.",
  },
  {
    topic: "Reading",
    q: "How can I check a story myself?",
    a: "Open the original Finnish version at the bottom of the story and compare. Read the community notes: members add context with a link to a source, and a note is only shown once people in different situations rate it helpful. Before you act on anything about permits, healthcare or tax, check with Migri, Kela or the City of Oulu.",
  },
  {
    topic: "Reading",
    q: "What does \"In English\" on a story mean?",
    a: "The story was translated into your language by machine and then checked. \"Translated by a person\" means a person translated it. If a story isn't in your language yet, you see the original with \"Not yet in\" and your language.",
  },
  {
    topic: "Reading",
    q: "What if a story is wrong?",
    a: "The newsroom corrects it, marks it \"Corrected\" and shows what changed. To report a mistake, use Ask the newsroom. If your correction is accepted, you earn 15 points.",
  },
  {
    topic: "Contributing",
    q: "How do I become a contributor?",
    a: "Write a post in one of your communities, add a photo or send a correction. Once an editor approves it you earn points, and at 10 points you are a Contributor. One approved post is enough.",
  },
  {
    topic: "Contributing",
    q: "What are Local guide and Trusted voice?",
    a: "Local guide needs 60 points and an average rating of 4.0 or more from at least 5 members. Trusted voice isn't reached with points: a community editor gives it based on your record, and your posts then carry a badge.",
  },
  {
    topic: "Contributing",
    q: "Why wasn't my post approved?",
    a: "Editors don't approve posts that repeat a rumour, can't be checked or break the community rules. A rejected or removed post takes 5 points off, so a few good posts count for more than many quick ones.",
  },
  {
    topic: "Contributing",
    q: "What happens to faces in my photos?",
    a: "Faces are blurred automatically when you upload a photo. A moderator then checks the photo before anyone else can see it.",
  },
  {
    topic: "Rewards",
    q: "How do I use my points?",
    a: "Your points set your level, and your level sets your discount at each partner. Open Rewards, tap a partner and tap Get code. Show it at the till, or enter it at checkout when you shop online. You get one code per partner each month, valid for 14 days.",
  },
  {
    topic: "Rewards",
    q: "How much off do I get?",
    a: "Each partner sets a discount for every level. At Hesburger, for example, it is 15% for a Contributor, 25% for a Local guide and 40% for a Trusted voice. Your discount is shown next to every partner in Rewards.",
  },
  {
    topic: "Rewards",
    q: "Can I get cash instead?",
    a: "No. Rewards are discounts from local partners. Paying money for posts would reward people for making things up.",
  },
  {
    topic: "Ad-free",
    q: "Can I read without ads?",
    a: "Yes, for €1 a month or €10 a year. The news, your communities and partner discounts are free either way. Ads are always marked as ads and never look like news.",
  },
  {
    topic: "Ad-free",
    q: "I'm a contributor. Can I still go ad-free?",
    a: "Yes. The ad-free plan and your contributor level are separate, so you keep your level and your discounts.",
  },
  {
    topic: "Ad-free",
    q: "How do I cancel?",
    a: "Go to Rewards, tap Ad-free, then Cancel plan. You stay ad-free until the end of the period you paid for.",
  },
];
const TOPICS = ["All", ...new Set(FAQS.map((f) => f.topic))];

function Question({ faq, open, onToggle }) {
  const Icon = open ? Minus : Plus;
  return (
    <div className={cn("rounded-card border transition-colors", open ? "border-ink bg-ink text-on-ink" : "border-line bg-surface")}>
      <button type="button" onClick={onToggle} aria-expanded={open}
        className="focus-ring flex w-full items-center gap-3 rounded-card px-4 py-3.5 text-left">
        <span className="flex-1 text-ui font-medium">{faq.q}</span>
        <span className={cn("grid h-6 w-6 shrink-0 place-items-center rounded-full", open ? "bg-on-ink text-ink" : "bg-ink text-on-ink")}>
          <Icon size={14} strokeWidth={2.5} />
        </span>
      </button>
      {open && <p className="px-4 pb-4 text-meta leading-relaxed opacity-85">{faq.a}</p>}
    </div>
  );
}

/** Help: short answers for readers, contributors and ad-free readers. */
export default function Help() {
  const [topic, setTopic] = useState("All");
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(FAQS[0].q);
  const q = search.trim().toLowerCase();
  const list = FAQS.filter((f) => (topic === "All" || f.topic === topic) && (!q || `${f.q} ${f.a}`.toLowerCase().includes(q)));

  return (
    <Page className="pb-12">
      <PageHeader back title="How can we help you?" />
      <div className="flex flex-col gap-4 pt-2">
        <div className="relative">
          <Search size={17} className="pointer-events-none absolute start-3 top-1/2 -translate-y-1/2 text-muted" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search questions" className="ps-9" aria-label="Search questions" />
        </div>
        <div className="-mx-4 flex gap-1 overflow-x-auto px-4 [scrollbar-width:none] sm:mx-0 sm:px-0">
          {TOPICS.map((t) => (
            <button key={t} type="button" onClick={() => setTopic(t)}
              className={cn("focus-ring h-9 shrink-0 rounded-control px-3 text-meta transition-colors",
                topic === t ? "bg-ink font-medium text-on-ink" : "text-muted hover:bg-sunk hover:text-ink")}>
              {t}
            </button>
          ))}
        </div>
        <div className="flex flex-col gap-2">
          {list.map((f) => <Question key={f.q} faq={f} open={open === f.q} onToggle={() => setOpen(open === f.q ? null : f.q)} />)}
          {!list.length && <p className="py-8 text-center text-ui text-muted">No questions match "{search}".</p>}
        </div>
        <div className="mt-6 flex flex-col items-start gap-3 border-t border-line pt-6">
          <h2 className="text-title">Didn't find your answer?</h2>
          <Button asChild variant="secondary"><Link to="/create">Ask the newsroom</Link></Button>
        </div>
      </div>
    </Page>
  );
}
