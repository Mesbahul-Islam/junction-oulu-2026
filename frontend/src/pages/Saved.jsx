import { useEffect, useState } from "react";

import NewsCard from "../components/NewsCard";
import { Spinner } from "../components/Spinner";
import { getSaved } from "../lib/api";

export default function Saved() {
  const [cards, setCards] = useState(null);
  useEffect(() => { getSaved().then(setCards); }, []);

  return (
    <main className="screen">
      <h1 className="title-serif">Saved</h1>
      <p className="lead">Stories you bookmarked.</p>
      {!cards ? <Spinner /> : cards.length ? (
        <div className="card-list">{cards.map((c, i) => <NewsCard key={c.id} card={c} index={i} />)}</div>
      ) : <div className="empty">Nothing saved yet. Tap the bookmark on a story to keep it here.</div>}
    </main>
  );
}
