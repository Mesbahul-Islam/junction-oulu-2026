import NewsCard from "../components/NewsCard";
import { useSaved } from "../hooks/useFeed";
import { Spinner } from "@/shared/components/Spinner";

export default function Saved() {
  const { data: cards, isLoading } = useSaved();

  return (
    <main className="screen">
      <h1 className="title-serif">Saved</h1>
      <p className="lead">Stories you bookmarked.</p>
      {isLoading ? <Spinner /> : cards?.length ? (
        <div className="card-list">{cards.map((c, i) => <NewsCard key={c.id} card={c} index={i} />)}</div>
      ) : <div className="empty">Nothing saved yet. Tap the bookmark on a story to keep it here.</div>}
    </main>
  );
}
