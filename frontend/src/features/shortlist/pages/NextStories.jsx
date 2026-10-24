import { ArrowRight, CircleCheck, ListPlus, PenLine, ThumbsUp, Users } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui";
import { Column, ColumnTitle, EmptyState, QueryBoundary, TrustBlock } from "@/components/patterns";
import { useAuth } from "@/features/auth/AuthProvider";
import { languageName } from "@/lib/i18n";
import { ProposalRow } from "../components/ProposalRow";
import { useShortlist } from "../hooks/useShortlist";

function Section({ title, count, children }) {
  return (
    <section className="border-b border-line">
      <h2 className="flex items-baseline gap-2 px-4 pb-1 pt-6 text-caption font-semibold uppercase tracking-wide text-muted sm:px-6">
        {title}{count != null && <span className="tabular-nums">{count}</span>}
      </h2>
      {children}
    </section>
  );
}

/** How a vote turns into a story, in three steps. */
function HowItWorks({ lang }) {
  const steps = [
    { icon: ThumbsUp, text: "You vote for stories the newsroom hasn't written yet." },
    { icon: PenLine, text: "Its next run writes the most-wanted ones, and an editor checks each." },
    { icon: CircleCheck, text: `You get the story in ${languageName(lang) || "your language"}, explained for you.` },
  ];
  return (
    <ol className="grid gap-3 px-4 py-5 sm:grid-cols-3 sm:gap-4 sm:px-6">
      {steps.map(({ icon: Icon, text }, i) => (
        <li key={text} className="flex items-start gap-3 sm:flex-col sm:gap-2">
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-sunk text-muted"><Icon size={15} /></span>
          <p className="text-meta text-ink/90"><span className="sr-only">Step {i + 1}: </span>{text}</p>
        </li>
      ))}
    </ol>
  );
}

/** Next stories: members choose what the newsroom covers next. */
export default function NextStories() {
  const { me } = useAuth();
  const query = useShortlist();
  const data = query.data;
  const open = data?.open || [];
  const covered = data?.covered || [];
  const maxVotes = Math.max(0, ...open.map((x) => x.votes));
  const myVotes = open.filter((x) => x.voted).length;

  return (
    <Column
      header={
        <ColumnTitle
          title="Next stories"
          subtitle="What should we cover next?"
          aside={myVotes > 0 && `You voted for ${myVotes}`}
        />
      }
    >
      <HowItWorks lang={me?.preferred_language} />

      {data && !data.member && (
        <div className="px-4 pb-5 sm:px-6">
          <TrustBlock
            tone="community"
            icon={Users}
            title="Join a community to vote"
            action={<Button asChild variant="secondary" size="sm"><Link to="/communities">Find your community<ArrowRight size={14} className="rtl:rotate-180" /></Link></Button>}
          >
            <p>Votes come from members, so every group is heard, however small.</p>
          </TrustBlock>
        </div>
      )}

      <QueryBoundary query={query} isEmpty={() => false}>
        <Section title="Open for votes" count={open.length}>
          {open.length === 0 ? (
            <EmptyState icon={ListPlus} title="Nothing to vote on right now">
              The newsroom adds stories it hasn't covered yet after each run.
            </EmptyState>
          ) : (
            <ol className="divide-y divide-line">
              {open.map((item, i) => (
                <li key={item.id} className="px-4 py-5 sm:px-6">
                  <ProposalRow item={item} rank={i + 1} maxVotes={maxVotes} canVote={data.member} />
                </li>
              ))}
            </ol>
          )}
          {open.length > 0 && maxVotes === 0 && (
            <p className="px-4 pb-5 text-meta text-muted sm:px-6">No votes yet. Yours puts a story first.</p>
          )}
        </Section>

        {covered.length > 0 && (
          <Section title="Your votes became stories" count={covered.length}>
            <ul className="divide-y divide-line">
              {covered.map((item) => (
                <li key={item.id} className="flex items-center gap-3 px-4 py-4 sm:px-6">
                  <CircleCheck size={18} className="shrink-0 text-confirmed" />
                  <div className="min-w-0 flex-1" dir="auto">
                    <p className="text-ui font-medium">{item.title}</p>
                    <p className="text-caption text-muted">Written after {item.votes === 1 ? "1 reader" : `${item.votes} readers`} voted</p>
                  </div>
                  {item.story ? (
                    <Button asChild variant="ghost" size="sm"><Link to={`/story/${item.story}`}>Read<ArrowRight size={14} className="rtl:rotate-180" /></Link></Button>
                  ) : (
                    <span className="text-caption text-muted">In the works</span>
                  )}
                </li>
              ))}
            </ul>
          </Section>
        )}
      </QueryBoundary>
    </Column>
  );
}
