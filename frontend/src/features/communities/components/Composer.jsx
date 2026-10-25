import { useQueryClient } from "@tanstack/react-query";
import { ImagePlus, Send, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Avatar, Button, Textarea, toast } from "@/components/ui";
import { useAuth } from "@/features/auth/AuthProvider";
import { createPost } from "../api";

// The server shrinks photos to 1600px anyway (communities/photos.py), so shrink before uploading:
// phone photos are often over the 10 MB limit. Formats the browser can't decode go as they are.
async function shrink(file) {
  try {
    const bmp = await createImageBitmap(file);
    const scale = Math.min(1, 1600 / Math.max(bmp.width, bmp.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bmp.width * scale);
    canvas.height = Math.round(bmp.height * scale);
    canvas.getContext("2d").drawImage(bmp, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.9));
    return blob ? new File([blob], "photo.jpg", { type: "image/jpeg" }) : file;
  } catch {
    return file;
  }
}

/** Ask or share something with one of your communities. `slug` preselects the community. */
export function Composer({ communities, slug }) {
  const { me } = useAuth();
  const queryClient = useQueryClient();
  const [body, setBody] = useState("");
  const [picked, setPicked] = useState(null);
  const [busy, setBusy] = useState(false);
  const [photo, setPhoto] = useState(null);
  const preview = useMemo(() => (photo ? URL.createObjectURL(photo) : null), [photo]);
  useEffect(() => () => preview && URL.revokeObjectURL(preview), [preview]);
  const target = slug || picked || (communities.find((c) => c.kind === "geo") || communities[0])?.slug;
  const name = communities.find((c) => c.slug === target)?.name;

  const send = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await createPost(target, body.trim(), photo);
      setBody("");
      setPhoto(null);
      toast({ title: `Posted to ${name}`, tone: "confirmed" });
      queryClient.invalidateQueries({ queryKey: ["posts"] });
    } catch (err) {
      toast({ title: "Your post wasn't sent", description: Object.values(err.data || {}).flat()[0] || err.message, tone: "danger" });
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
        {preview && (
          <div className="flex items-start gap-3">
            <div className="relative">
              <img src={preview} alt="Photo to post" className="h-24 w-auto max-w-[12rem] rounded-control border border-line object-cover" />
              <button type="button" onClick={() => setPhoto(null)} aria-label="Remove photo" className="focus-ring absolute end-1 top-1 grid h-6 w-6 place-items-center rounded-full bg-ink/70 text-on-ink">
                <X size={14} />
              </button>
            </div>
            <p className="text-caption text-muted">Faces are blurred automatically when you post. A moderator checks the photo before others see it.</p>
          </div>
        )}
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
          {!photo && (
            <label className="inline-flex h-8 cursor-pointer focus-within:outline focus-within:outline-2 focus-within:outline-ink items-center gap-1.5 rounded-control px-2 text-meta text-muted hover:bg-ink/5 hover:text-ink [@media(pointer:coarse)]:h-11">
              <ImagePlus size={16} />Photo
              <input type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" onChange={async (e) => { const f = e.target.files?.[0]; setPhoto(f ? await shrink(f) : null); }} />
            </label>
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
