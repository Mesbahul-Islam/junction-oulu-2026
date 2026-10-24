import { useQueryClient } from "@tanstack/react-query";
import { Send } from "lucide-react";
import { useState } from "react";

import { Avatar, Button, Textarea, toast } from "@/components/ui";
import { useAuth } from "@/features/auth/AuthProvider";
import { createPost } from "../api";

/** Ask or share something with one of your communities. `slug` preselects the community. */
export function Composer({ communities, slug }) {
  const { me } = useAuth();
  const queryClient = useQueryClient();
  const [body, setBody] = useState("");
  const [picked, setPicked] = useState(null);
  const [busy, setBusy] = useState(false);
  const target = slug || picked || (communities.find((c) => c.kind === "geo") || communities[0])?.slug;
  const name = communities.find((c) => c.slug === target)?.name;

  const send = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await createPost(target, body.trim());
      setBody("");
      toast({ title: `Posted to ${name}`, tone: "confirmed" });
      queryClient.invalidateQueries({ queryKey: ["posts"] });
    } catch (err) {
      toast({ title: "Your post wasn't sent", description: err.message, tone: "danger" });
    } finally {
      setBusy(false);
    }
  };

  if (!communities.length) return null;
  return (
    <form onSubmit={send} className="flex gap-3 border-b border-line px-4 py-4 sm:px-6">
      <Avatar name={me?.username} size="md" className="hidden sm:grid" />
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <Textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          dir="auto"
          maxLength={4000}
          placeholder={`Ask or share something with ${name}`}
          aria-label="New post"
          className="min-h-[72px]"
        />
        <div className="flex flex-wrap items-center gap-2">
          {!slug && communities.length > 1 && (
            <select
              value={target}
              onChange={(e) => setPicked(e.target.value)}
              aria-label="Post to"
              className="focus-ring h-8 max-w-[60%] truncate rounded-control border border-line bg-surface px-2 text-meta text-ink [@media(pointer:coarse)]:h-11"
            >
              {communities.map((c) => <option key={c.slug} value={c.slug}>{c.name}</option>)}
            </select>
          )}
          <p className="hidden flex-1 text-caption text-muted sm:block">Members read it in their language. Not checked by editors.</p>
          <Button type="submit" size="sm" className="ms-auto" disabled={busy || !body.trim()}>
            <Send size={14} className="rtl:rotate-180" />Post
          </Button>
        </div>
      </div>
    </form>
  );
}
