import { Bookmark } from "lucide-react";

import { Column, ColumnTitle, EmptyState, QueryBoundary } from "@/components/patterns";
import { useAuth } from "@/features/auth/AuthProvider";
import { StoryRow } from "../components/StoryRow";
import { useSaved } from "../hooks/useFeed";

/** Stories the reader bookmarked, newest save first. */
export default function Saved() {
  const { me } = useAuth();
  const query = useSaved();
  return (
    <Column header={<ColumnTitle title="Saved" subtitle="Stories you bookmarked" />}>
      <QueryBoundary
        query={query}
        empty={<EmptyState icon={Bookmark} title="Nothing saved yet">Tap the bookmark on a story to keep it here.</EmptyState>}
      >
        {(cards) => cards.map((c) => <StoryRow key={c.id} card={c} lang={me?.preferred_language} />)}
      </QueryBoundary>
    </Column>
  );
}
