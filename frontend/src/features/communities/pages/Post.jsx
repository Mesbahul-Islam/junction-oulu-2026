import { ChevronLeft } from "lucide-react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import { Column } from "@/components/patterns";
import { Button } from "@/components/ui";
import { transitionTo } from "@/lib/transition";
import { Thread } from "../components/Thread";

/** A community thread on its own page, opened from Community (replacing it; Back returns) or a
 *  shared link. Same Column frame as the list, so only the content changes when it opens. */
export default function Post() {
  const { slug, id } = useParams();
  const navigate = useNavigate();
  const { state, key } = useLocation(); // the post from the list, shown while the fresh copy loads
  // A shared link opened fresh has nothing to go back to: Back goes to Community instead.
  const back = () => transitionTo(() => (key !== "default" ? navigate(-1) : navigate("/communities")), `p${id}`);
  return (
    <Column
      header={
        <div className="flex min-h-14 items-center px-4 pt-[env(safe-area-inset-top)] sm:px-6">
          <Button variant="ghost" size="sm" className="-ms-2.5" onClick={back}>
            <ChevronLeft size={16} className="rtl:rotate-180" />Back
          </Button>
        </div>
      }
    >
      <div className="px-4 pb-16 pt-6 sm:px-6">
        <Thread slug={slug} id={id} placeholder={state?.id === Number(id) ? state : undefined} onGone={back} size="page" />
      </div>
    </Column>
  );
}
