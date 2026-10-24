import { BadgeCheck } from "lucide-react";

/** Shown next to a trusted voice's name: someone whose notes and questions the community verified,
 *  approved by an editor. */
export default function TrustBadge() {
  return (
    <span className="trust-badge" title="Trusted voice: verified by the community and approved by an editor">
      <BadgeCheck size={13} /> Trusted voice
    </span>
  );
}
