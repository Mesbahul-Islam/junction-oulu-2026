import { ChevronLeft } from "lucide-react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import { Page } from "@/components/patterns";
import { Button } from "@/components/ui";
import { useAuth } from "@/features/auth/AuthProvider";
import { StoryView } from "../components/StoryView";

/** A story on its own page: phones (tapped from the feed) and shared links. */
export default function Story() {
  const { id } = useParams();
  const { me } = useAuth();
  const navigate = useNavigate();
  const { state } = useLocation(); // the feed card, if we came from the feed (has the ranking)
  const card = state?.id === Number(id) ? state : undefined;
  return (
    <Page className="pb-16">
      <div className="flex min-h-14 items-center pt-[env(safe-area-inset-top)] lg:pt-6">
        <Button variant="ghost" size="sm" className="-ms-2.5" onClick={() => (window.history.length > 1 ? navigate(-1) : navigate("/"))}>
          <ChevronLeft size={16} className="rtl:rotate-180" />Back
        </Button>
      </div>
      <StoryView id={id} card={card} ranking={card?.ranking} lang={me?.preferred_language} size="page" onReported={() => navigate("/")} />
    </Page>
  );
}
