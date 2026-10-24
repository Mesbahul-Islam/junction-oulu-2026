import { BadgeCheck } from "lucide-react";

import { Badge } from "@/components/ui";

/** Shown next to a trusted voice's name: someone whose notes and questions the community verified,
 *  approved by an editor. Spruce = people confirmed it. */
export default function TrustBadge() {
  return (
    <Badge tone="confirmed" title="Trusted voice: verified by the community and approved by an editor">
      <BadgeCheck size={12} />Trusted voice
    </Badge>
  );
}
