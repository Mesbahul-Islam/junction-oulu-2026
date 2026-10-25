import { useQueryClient } from "@tanstack/react-query";
import { Flag, Flame, Heart, Image as ImageIcon, Languages, MessageCircle, Newspaper, Share2, ShieldAlert, Trash2, Users } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { Avatar, Badge, Button, Dialog, DialogClose, DialogContent, DialogTrigger, RadioCards, toast } from "@/components/ui";
import { TrustBlock } from "@/components/patterns";
import TrustBadge from "@/features/trust/components/TrustBadge";
import { useTrustedVoices } from "@/features/trust/hooks";
import { languageName, timeAgo } from "@/lib/i18n";
import { transitionTo } from "@/lib/transition";
import { cn } from "@/lib/utils";
import { deletePost, flagPost, likePost, sharePost } from "../api";

export const postHref = (p) => `/communities/${p.community_slug}/posts/${p.id}`;
const host = (u) => { try { return new URL(u).hostname.replace(/^www\./, ""); } catch { return u; } };

const REASONS = [
  { value: "false", label: "False or misleading", hint: "It stays up and members are asked to add context." },
  { value: "hate", label: "Hate or harassment", hint: "Hidden until a moderator reviews it." },
  { value: "privacy", label: "Violates someone's privacy", hint: "Hidden until a moderator reviews it." },
  { value: "spam", label: "Spam or advertising", hint: "Hidden until a moderator reviews it." },
  { value: "other", label: "Something else", hint: "Hidden until a moderator reviews it." },
];

/** Who wrote it, where and when; the text in the reader's language (original a tap away);
 *  and what the newsroom and other readers added. Shared by the timeline row and the thread. */
export function PostBody({ post, lang, size = "row", onAddContext, link }) {
  const isTrusted = useTrustedVoices();
  const [original, setOriginal] = useState(false);
  const t = post.translation && !original ? post.translation : null;
  const note = post.community_note;
  const noteT = note?.translation && !original ? note.translation : null;
  const text = (
    <p dir="auto" data-story-part="body" lang={t ? t.language : post.language} className={cn("whitespace-pre-line text-ink", size === "row" ? "text-ui" : "text-body")}>
      {t ? t.text : post.body}
    </p>
  );
  return (
    <div data-story={`p${post.id}`} className="flex gap-3">
      <Avatar name={post.author_name} size={size === "row" ? "md" : "lg"} community data-story-part="avatar" />
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-meta">
          <span className="font-medium text-ink">{post.author_name}</span>
          {isTrusted(post.author, post.community_slug) && <TrustBadge />}
          <span className="text-muted">in {post.community_name}</span>
          <span className="text-muted" aria-hidden="true">·</span>
          <time dateTime={post.created_at} className="text-muted">{timeAgo(post.created_at, lang)}</time>
          {post.kind === "announcement" && <Badge tone="community">Announcement</Badge>}
          {post.hot && <Badge tone="community" appearance="outline"><Flame size={12} />Popular</Badge>}
        </p>
        {post.status === "hidden" && post.is_mine && (
          <p className="text-caption text-danger">Hidden from others while a moderator reviews a report.</p>
        )}
        {link ? <Link {...link} className="focus-ring block rounded-control hover:opacity-80">{text}</Link> : text}
        {post.image && (
          <figure className="flex flex-col gap-1.5">
            <img src={post.image} alt="" loading="lazy" data-story-part="image" className={cn("w-full rounded-card border border-line bg-sunk object-cover", size === "row" ? "max-h-72" : "max-h-[28rem]")} />
            {(post.image_status === "pending" || post.faces_blurred > 0) && (
              <figcaption className="flex flex-wrap gap-x-3 text-caption text-muted">
                {post.image_status === "pending" && <span className="text-community">Only you can see this photo until a moderator checks it</span>}
                {post.faces_blurred > 0 && <span>Faces blurred automatically</span>}
              </figcaption>
            )}
          </figure>
        )}
        {!post.image && post.image_status === "pending" && (
          // Others get no image until a moderator checks the blurring; say a photo is on its way.
          <p className={cn("flex items-center gap-2 rounded-card border border-dashed border-line bg-sunk/60 px-3 text-meta text-muted", size === "row" ? "py-3" : "py-6")}>
            <ImageIcon size={16} className="shrink-0" />A photo is waiting for a moderator to check it
          </p>
        )}
        {post.image_status === "rejected" && post.is_mine && (
          <p className="text-caption text-danger">A moderator removed your photo. Your text is still up.</p>
        )}
        {post.translation && (
          <button type="button" onClick={() => setOriginal(!original)} className="focus-ring inline-flex w-fit items-center gap-1 rounded-control text-caption text-muted hover:text-ink">
            <Languages size={12} />
            {original ? `Show in ${languageName(post.translation.language)}` : `Machine-translated from ${languageName(post.translation.from_language)} · show original`}
          </button>
        )}

        {post.answered_by && (
          <Link to={`/story/${post.answered_by.snippet}`} className="focus-ring group mt-1 flex items-start gap-3 rounded-card border border-newsroom/30 bg-newsroom-weak/50 p-3">
            <Newspaper size={16} className="mt-0.5 shrink-0 text-newsroom" />
            <span className="min-w-0">
              <span className="block text-caption font-semibold text-newsroom">Answered by the newsroom</span>
              <span className="block text-meta text-ink group-hover:underline" dir="auto">{post.answered_by.headline}</span>
            </span>
          </Link>
        )}
        {note && (
          <TrustBlock tone="confirmed" icon={Users} title="Readers added context" className="mt-1">
            <p className="font-medium" dir="auto">{noteT ? noteT.claim_summary : note.claim_summary}</p>
            <p dir="auto">{noteT ? noteT.context : note.context}</p>
            <p className="flex flex-wrap gap-x-3 text-meta">
              {note.citation_urls.map((u) => <a key={u} href={u} target="_blank" rel="noreferrer" className="underline decoration-line underline-offset-2 hover:decoration-ink">{host(u)}</a>)}
            </p>
          </TrustBlock>
        )}
        {!note && post.misleading_reports > 0 && (
          <button type="button" onClick={onAddContext} className="focus-ring mt-1 flex w-fit items-center gap-2 rounded-control text-meta text-danger hover:underline">
            <ShieldAlert size={15} />Readers say this may be misleading · Add context
          </button>
        )}
      </div>
    </div>
  );
}

function ReportDialog({ post, onDone }) {
  const [reason, setReason] = useState("false");
  const [busy, setBusy] = useState(false);
  const send = async () => {
    setBusy(true);
    try {
      const res = await flagPost(post.community_slug, post.id, reason);
      toast({ title: "Thanks for reporting", description: res.detail, tone: "confirmed" });
      onDone?.(res.hidden);
    } catch (e) {
      toast({ title: "Your report wasn't sent", description: e.message, tone: "danger" });
    } finally {
      setBusy(false);
    }
  };
  return (
    <DialogContent title="Report this post" description="Moderators are members of this community.">
      <RadioCards
        value={reason}
        onValueChange={setReason}
        options={REASONS}
        renderOption={(o) => <span className="flex flex-col"><span className="text-ui">{o.label}</span><span className="text-caption text-muted">{o.hint}</span></span>}
      />
      <div className="flex justify-end gap-2">
        <DialogClose asChild><Button variant="ghost">Cancel</Button></DialogClose>
        <DialogClose asChild><Button onClick={send} disabled={busy}>Report</Button></DialogClose>
      </div>
    </DialogContent>
  );
}

const iconBtn = "focus-ring inline-flex h-9 min-w-9 items-center justify-center gap-1.5 rounded-control px-2 text-meta text-muted transition-colors hover:bg-ink/5 hover:text-ink [@media(pointer:coarse)]:h-11 [@media(pointer:coarse)]:min-w-11";

/** Like, reply, share, report (or delete your own). `onReply` opens the thread. */
export function PostActions({ post, onReply, onGone }) {
  const queryClient = useQueryClient();
  const [liked, setLiked] = useState(!!post.liked);
  const [likes, setLikes] = useState(post.like_count || 0);
  const like = async () => {
    setLiked(!liked);
    setLikes(likes + (liked ? -1 : 1));
    try {
      const res = await likePost(post.community_slug, post.id, !liked);
      setLiked(res.liked);
      setLikes(res.like_count);
    } catch (e) {
      setLiked(liked);
      setLikes(likes);
      toast({ title: "Couldn't like the post", description: e.message, tone: "danger" });
    }
  };
  const share = async () => {
    const url = `${window.location.origin}${postHref(post)}`;
    if (navigator.share) await navigator.share({ text: post.body, url }).catch(() => {});
    else {
      await navigator.clipboard?.writeText(url);
      toast({ title: "Link copied" });
    }
    sharePost(post.community_slug, post.id).catch(() => {});
  };
  const remove = async () => {
    try {
      await deletePost(post.community_slug, post.id);
      toast({ title: "Post deleted" });
      queryClient.invalidateQueries({ queryKey: ["posts"] });
      onGone?.();
    } catch (e) {
      toast({ title: "Couldn't delete the post", description: e.message, tone: "danger" });
    }
  };
  const gone = (hidden) => {
    if (!hidden) return queryClient.invalidateQueries({ queryKey: ["posts"] });
    queryClient.invalidateQueries({ queryKey: ["posts"] });
    onGone?.();
  };

  return (
    <div className="-ms-2 flex items-center gap-1">
      <button type="button" className={iconBtn} onClick={onReply} aria-label={`Replies (${post.reply_count || 0})`}>
        <MessageCircle size={16} />{post.reply_count > 0 && post.reply_count}
      </button>
      <button type="button" className={cn(iconBtn, liked && "text-community")} onClick={like} aria-pressed={liked} aria-label={`Like (${likes})`}>
        <Heart size={16} fill={liked ? "currentColor" : "none"} />{likes > 0 && likes}
      </button>
      <button type="button" className={iconBtn} onClick={share} aria-label="Share"><Share2 size={16} /></button>
      <Dialog>
        {post.is_mine ? (
          <>
            <DialogTrigger className={cn(iconBtn, "ms-auto")} aria-label="Delete your post"><Trash2 size={16} /></DialogTrigger>
            <DialogContent title="Delete your post?" description="It's removed for everyone, with its replies.">
              <div className="flex justify-end gap-2">
                <DialogClose asChild><Button variant="ghost">Cancel</Button></DialogClose>
                <DialogClose asChild><Button variant="danger" onClick={remove}>Delete</Button></DialogClose>
              </div>
            </DialogContent>
          </>
        ) : (
          <>
            <DialogTrigger className={cn(iconBtn, "ms-auto")} aria-label="Report this post"><Flag size={16} /></DialogTrigger>
            <ReportDialog post={post} onDone={gone} />
          </>
        )}
      </Dialog>
    </div>
  );
}

/** A member's post in the Community timeline. Opens its thread in the side peek (tablet up)
 *  or on its own page. */
/** A post in the Community timeline. Opening it (the text, Reply, a note to rate) shows the
 *  thread as a page with a view transition; `onOpen(post)` overrides that. */
export function PostRow({ post, lang, onOpen, active }) {
  const navigate = useNavigate();
  const open = (e) => {
    if (e?.metaKey || e?.ctrlKey || e?.shiftKey) return;
    e?.preventDefault();
    if (onOpen) onOpen(post);
    else transitionTo(() => navigate(postHref(post), { state: post }), `p${post.id}`);
  };
  return (
    <article className={cn("border-b border-line px-4 py-4 sm:px-6", active && "bg-sunk/60")}>
      <PostBody post={post} lang={lang} link={{ to: postHref(post), state: post, onClick: open }} onAddContext={open} />
      <div className="ms-12 mt-1">
        <PostActions post={post} onReply={open} />
        {post.notes_to_rate > 0 && (
          <button type="button" onClick={open} className="focus-ring mt-1 inline-flex items-center gap-1.5 rounded-control text-caption text-muted hover:text-ink">
            <Users size={13} />{post.notes_to_rate === 1 ? "A reader note needs your rating" : `${post.notes_to_rate} reader notes need your rating`}
          </button>
        )}
      </div>
    </article>
  );
}
