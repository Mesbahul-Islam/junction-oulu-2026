import { useQueryClient } from "@tanstack/react-query";
import { Send } from "lucide-react";
import { useRef, useState } from "react";

import { Avatar, Button, Textarea, toast } from "@/components/ui";
import { QueryBoundary } from "@/components/patterns";
import { useAuth } from "@/features/auth/AuthProvider";
import { PostNotes } from "@/features/notes/components/PostNotes";
import { replyToPost } from "../api";
import { usePost, useReplies } from "../hooks/useCommunities";
import { PostActions, PostBody } from "./Post";

function ReplyForm({ post, onSent }) {
  const { me } = useAuth();
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const send = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await replyToPost(post.community_slug, post.id, body.trim());
      setBody("");
      onSent();
    } catch (err) {
      toast({ title: "Your reply wasn't sent", description: err.message, tone: "danger" });
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={send} className="flex items-start gap-3">
      <Avatar name={me?.username} size="sm" className="mt-1" />
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <Textarea
          id={`reply-${post.id}`}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          dir="auto"
          maxLength={4000}
          placeholder={`Reply to ${post.author_name}`}
          aria-label={`Reply to ${post.author_name}`}
          className="min-h-[72px]"
        />
        <div className="flex items-center justify-between gap-3">
          <p className="text-caption text-muted">Neighbours who read other languages see it translated.</p>
          <Button type="submit" size="sm" disabled={busy || !body.trim()}><Send size={14} className="rtl:rotate-180" />Reply</Button>
        </div>
      </div>
    </form>
  );
}

/** A post with its reader notes and replies: in the side peek or on its own page. */
export function Thread({ slug, id, placeholder, onGone, size = "peek" }) {
  const { me } = useAuth();
  const lang = me?.preferred_language;
  const queryClient = useQueryClient();
  const query = usePost(slug, id, placeholder);
  const replies = useReplies(slug, id);
  const notesRef = useRef(null);
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["post", Number(id)] });
    queryClient.invalidateQueries({ queryKey: ["replies", Number(id)] });
    queryClient.invalidateQueries({ queryKey: ["posts"] });
  };

  return (
    <QueryBoundary query={query} isEmpty={() => false}>
      {(post) => {
        // Notes come first when there's something to read or rate; otherwise after the replies.
        const notesFirst = post.community_note || post.misleading_reports > 0 || post.notes_to_rate > 0;
        const notes = (
          <div ref={notesRef} className="border-t border-line pt-5">
            <PostNotes post={post} onChanged={refresh} />
          </div>
        );
        return (
          <div className="flex flex-col gap-5">
            <div>
              <PostBody post={post} lang={lang} size={size} onAddContext={() => notesRef.current?.scrollIntoView({ behavior: "smooth" })} />
              <div className="ms-14 mt-2">
                <PostActions key={post.id} post={post} onReply={() => document.getElementById(`reply-${post.id}`)?.focus()} onGone={onGone} />
              </div>
            </div>
            {notesFirst && notes}
            <section aria-labelledby={`replies-${post.id}`} className="border-t border-line pt-5">
              <h2 id={`replies-${post.id}`} className="text-title">
                Replies{replies.data?.length ? <span className="ms-2 text-muted">{replies.data.length}</span> : null}
              </h2>
              <div className="mt-4">
                <ReplyForm post={post} onSent={refresh} />
              </div>
              <QueryBoundary query={replies} empty={<p className="py-5 text-meta text-muted">No replies yet. Be the first to help.</p>}>
                {(list) => (
                  <ul className="mt-2 divide-y divide-line">
                    {list.map((r) => (
                      <li key={r.id} className="py-4">
                        <PostBody post={r} lang={lang} />
                        <div className="ms-12 mt-1"><PostActions post={r} onReply={() => document.getElementById(`reply-${post.id}`)?.focus()} onGone={refresh} /></div>
                      </li>
                    ))}
                  </ul>
                )}
              </QueryBoundary>
            </section>
            {!notesFirst && notes}
          </div>
        );
      }}
    </QueryBoundary>
  );
}
