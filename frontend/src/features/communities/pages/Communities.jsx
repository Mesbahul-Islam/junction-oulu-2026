import { Compass, Users } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { Button, Spinner } from "@/components/ui";
import { Column, ColumnTitle, EmptyState, FilterBar, FilterChip, QueryBoundary, SidePeek, useCanPeek } from "@/components/patterns";
import { useAuth } from "@/features/auth/AuthProvider";
import { Composer } from "../components/Composer";
import { PostRow, postHref } from "../components/Post";
import { Thread } from "../components/Thread";
import { useCommunities, usePosts } from "../hooks/useCommunities";

/** Community: what members of your communities ask and share, newest first. */
export default function Communities() {
  const { me } = useAuth();
  const lang = me?.preferred_language;
  const [params, setParams] = useSearchParams();
  const slug = params.get("c");
  const peek = params.get("post"); // "<community slug>/<post id>"
  const canPeek = useCanPeek();
  const groups = useCommunities();
  const posts = usePosts(slug);
  const [peekPost, setPeekPost] = useState(null);

  const mine = (groups.data?.all || []).filter((g) => g.is_member);
  const setParam = (key, value, replace) => setParams((p) => {
    const next = new URLSearchParams(p);
    if (value) next.set(key, value); else next.delete(key);
    return next;
  }, { replace });
  const openPost = canPeek ? (p) => { setPeekPost(p); setParam("post", `${p.community_slug}/${p.id}`); } : undefined;
  const closePeek = () => setParam("post", null);
  const [peekSlug, peekId] = (peek || "").split("/");
  const peekPlaceholder = peekPost?.id === Number(peekId) ? peekPost : posts.data?.find((p) => p.id === Number(peekId));

  const endRef = useRef(null);
  useEffect(() => {
    if (!endRef.current || !posts.hasNextPage) return;
    const io = new IntersectionObserver(([e]) => e.isIntersecting && !posts.isFetchingNextPage && posts.fetchNextPage(), { rootMargin: "600px" });
    io.observe(endRef.current);
    return () => io.disconnect();
  }, [posts]);

  const noGroups = groups.data && mine.length === 0;
  return (
    <Column
      header={
        <>
          <ColumnTitle
            title="Community"
            subtitle="Your neighbours' words, not checked by editors"
            aside={<Button asChild variant="ghost" size="sm"><Link to="/communities/browse"><Compass size={15} />Find communities</Link></Button>}
          />
          {mine.length > 1 && (
            <FilterBar label="Communities">
              <FilterChip active={!slug} onClick={() => setParam("c", null, true)}>All</FilterChip>
              {mine.map((g) => (
                <FilterChip key={g.slug} active={slug === g.slug} onClick={() => setParam("c", slug === g.slug ? null : g.slug, true)}>{g.name}</FilterChip>
              ))}
            </FilterBar>
          )}
        </>
      }
    >
      {noGroups ? (
        <EmptyState
          icon={Users}
          title="Join a community"
          action={<Button asChild><Link to="/communities/browse">Find communities</Link></Button>}
        >
          Ask questions and help neighbours: newcomers, students, families, fans. Posts are translated into each member's language.
        </EmptyState>
      ) : (
        <>
          <Composer communities={mine} slug={slug} />
          <QueryBoundary
            query={posts}
            isEmpty={(d) => !d?.length}
            empty={<EmptyState icon={Users} title="No posts yet">Start the conversation: ask something or share a tip.</EmptyState>}
          >
            {(list) => (
              <>
                {list.map((p) => (
                  <PostRow key={p.id} post={p} lang={lang} onOpen={openPost} active={peek === `${p.community_slug}/${p.id}`} />
                ))}
                <div ref={endRef} className="grid place-items-center py-10">
                  {posts.isFetchingNextPage ? <Spinner /> : !posts.hasNextPage && <p className="text-meta text-muted">That's everything.</p>}
                </div>
              </>
            )}
          </QueryBoundary>
        </>
      )}

      {canPeek && peekId && (
        <SidePeek id={peek} label="Thread" href={postHref({ community_slug: peekSlug, id: peekId })} state={peekPlaceholder} onClose={closePeek}>
          <Thread key={peek} slug={peekSlug} id={peekId} placeholder={peekPlaceholder} onGone={closePeek} />
        </SidePeek>
      )}
    </Column>
  );
}
