import { BadgeCheck } from "lucide-react";

import { Badge } from "@/components/ui";
import { useMyTrust } from "../hooks";

const LEVEL = {
  member: "Member",
  contributor: "Contributor",
  eligible: "Waiting for an editor",
  trusted: "Trusted voice",
  paused: "Trusted voice, paused",
};
const SIGNAL = {
  helpful_note: "helpful notes",
  unhelpful_note: "notes rated not helpful",
  accepted_contribution: "questions and tips accepted",
  contribution_in_story: "became a story",
  story_candidate: "questions others asked too",
  like: "likes from others",
  good_rating: "ratings that matched",
  removed_post: "posts removed",
};

function Next({ t }) {
  const n = t.next || {};
  const say = (text) => <p className="mt-1.5 text-meta text-ink/85">{text}</p>;
  if (t.level === "eligible") return say("An editor of this community will review your standing.");
  if (t.level === "paused") return say("Raise your score or keep posts within the rules to restore it.");
  if (n.level === "contributor") return say(`${n.points} more points to Contributor.`);
  if (n.level === "eligible") {
    const parts = [n.points > 0 && `${n.points} more points`, n.verified > 0 && `${n.verified} more helpful note or accepted question`].filter(Boolean);
    return parts.length ? say(`To become a trusted voice: ${parts.join(" and ")}.`) : null;
  }
  return null;
}

/** You page: your standing in each community, what earned it, and the next step. */
export default function StandingCard() {
  const { data } = useMyTrust();
  if (!data?.length) return null;
  return (
    <div className="flex flex-col gap-1 py-3.5">
      <p className="text-ui font-medium">Your standing</p>
      <ul className="divide-y divide-line">
        {data.map((t) => (
          <li key={t.id} className="py-3">
            <div className="flex items-center justify-between gap-3">
              <span className="text-ui">{t.community_name}</span>
              <Badge tone={t.level === "trusted" ? "confirmed" : t.level === "eligible" ? "community" : "neutral"}>
                {t.level === "trusted" && <BadgeCheck size={12} />}{LEVEL[t.level]}
              </Badge>
            </div>
            <p className="mt-0.5 text-meta tabular-nums text-muted">{t.score} points</p>
            {Object.keys(t.breakdown).length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {Object.entries(t.breakdown).map(([k, v]) => (
                  <span key={k} className="rounded-pill bg-sunk px-2.5 py-0.5 text-caption text-muted">{v.count} {SIGNAL[k] || k}</span>
                ))}
              </div>
            )}
            <Next t={t} />
          </li>
        ))}
      </ul>
      <p className="text-caption text-muted">
        Points come from what others verify: notes rated helpful by people in different situations, questions the editors accepted, and likes. An editor approves trusted voices.
      </p>
    </div>
  );
}
