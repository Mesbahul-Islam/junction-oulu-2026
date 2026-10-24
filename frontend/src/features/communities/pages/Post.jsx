import { ChevronLeft } from "lucide-react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import { Page } from "@/components/patterns";
import { Button } from "@/components/ui";
import { Thread } from "../components/Thread";

/** A community thread on its own page: phones, and shared links. */
export default function Post() {
  const { slug, id } = useParams();
  const navigate = useNavigate();
  const { state } = useLocation(); // the post from the list, shown while the fresh copy loads
  const back = () => (window.history.length > 1 ? navigate(-1) : navigate("/communities"));
  return (
    <Page className="pb-16">
      <div className="flex min-h-14 items-center pt-[env(safe-area-inset-top)] lg:pt-6">
        <Button variant="ghost" size="sm" className="-ms-2.5" onClick={back}>
          <ChevronLeft size={16} className="rtl:rotate-180" />Back
        </Button>
      </div>
      <Thread slug={slug} id={id} placeholder={state?.id === Number(id) ? state : undefined} onGone={back} size="page" />
    </Page>
  );
}
