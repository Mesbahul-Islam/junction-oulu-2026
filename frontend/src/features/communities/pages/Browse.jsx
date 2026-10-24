import { useQueryClient } from "@tanstack/react-query";
import { Check, ChevronLeft, Hash, MapPin, Plus } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Button, toast } from "@/components/ui";
import { Column, ColumnTitle, QueryBoundary } from "@/components/patterns";
import { languageName, SITUATIONS } from "@/lib/i18n";
import { joinCommunity, leaveCommunity } from "../api";
import { useCommunities } from "../hooks/useCommunities";

const forWhom = (audiences) => audiences?.map((a) => SITUATIONS.find((s) => s.value === a)?.short).filter(Boolean);

function Group({ group, onChange }) {
  const [busy, setBusy] = useState(false);
  const Icon = group.kind === "geo" ? MapPin : Hash;
  const audience = forWhom(group.audiences);
  const toggle = async () => {
    setBusy(true);
    try {
      await (group.is_member ? leaveCommunity(group.slug) : joinCommunity(group.slug));
      toast({ title: group.is_member ? `You left ${group.name}` : `You joined ${group.name}`, tone: "confirmed" });
      await onChange();
    } catch (e) {
      toast({ title: "That didn't work", description: e.message, tone: "danger" });
    } finally {
      setBusy(false);
    }
  };
  return (
    <li className="flex items-start gap-3 px-4 py-4 sm:px-6">
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-control bg-community-weak text-community"><Icon size={16} /></span>
      <div className="min-w-0 flex-1">
        <h3 className="text-title">{group.name}</h3>
        {group.description && <p className="mt-0.5 text-meta text-ink/85">{group.description}</p>}
        {group.reasons?.length > 0 && (
          <p className="mt-1.5 text-caption font-medium text-ink">{group.reasons.join(" · ")}</p>
        )}
        <p className="mt-1.5 text-caption text-muted">
          {group.member_count === 1 ? "1 member" : `${group.member_count} members`}
          {audience?.length > 0 && ` · for ${audience.join(", ")}`}
          {group.languages?.length > 0 && ` · ${group.languages.map(languageName).join(", ")}`}
        </p>
      </div>
      <Button variant={group.is_member ? "ghost" : "secondary"} size="sm" onClick={toggle} disabled={busy} aria-pressed={group.is_member}>
        {group.is_member ? <><Check size={14} />Joined</> : <><Plus size={14} />Join</>}
      </Button>
    </li>
  );
}

function Section({ title, groups, onChange }) {
  if (!groups.length) return null;
  return (
    <section className="border-b border-line">
      <h2 className="px-4 pb-1 pt-6 text-caption font-semibold uppercase tracking-wide text-muted sm:px-6">{title}</h2>
      <ul className="divide-y divide-line">{groups.map((g) => <Group key={g.slug} group={g} onChange={onChange} />)}</ul>
    </section>
  );
}

/** Find communities: yours, ones matched to your profile (with why), and the rest. */
export default function Browse() {
  const query = useCommunities();
  const queryClient = useQueryClient();
  const refresh = async () => {
    await query.refetch();
    queryClient.invalidateQueries({ queryKey: ["posts"] });
    queryClient.invalidateQueries({ queryKey: ["shortlist"] }); // voting needs a membership
  };
  return (
    <Column
      header={
        <>
          <div className="px-2 pt-[max(0.5rem,env(safe-area-inset-top))] sm:px-4 lg:pt-4">
            <Button asChild variant="ghost" size="sm"><Link to="/communities"><ChevronLeft size={16} className="rtl:rotate-180" />Community</Link></Button>
          </div>
          <ColumnTitle title="Find communities" subtitle="Groups by place and by situation. Members' posts are translated for each other." />
        </>
      }
    >
      <QueryBoundary query={query} isEmpty={() => false}>
        {({ all, suggested }) => {
          const suggestedSlugs = new Set(suggested.map((g) => g.slug));
          return (
            <>
              <Section title="Suggested for you" groups={suggested.filter((g) => !g.is_member)} onChange={refresh} />
              <Section title="Your communities" groups={all.filter((g) => g.is_member)} onChange={refresh} />
              <Section title="More communities" groups={all.filter((g) => !g.is_member && !suggestedSlugs.has(g.slug))} onChange={refresh} />
            </>
          );
        }}
      </QueryBoundary>
    </Column>
  );
}
