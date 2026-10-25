// Animated route changes with the View Transitions API. The old screen is captured, `navigate`
// runs, and the new screen is captured once AppShell has committed it and set its scroll
// (routeCommitted). Only the item being opened (or returned to) is named, so its parts morph
// between its row and its page; everything else cross-fades. Items are stories (id) and
// community posts ("p" + id).
// No API or reduced motion: plain navigation.
let committed = null;
let active = null;

// Elements mark themselves with data-story="<id>" and, inside it, data-story-part="headline|body|avatar|image".
function nameStory(id) {
  document.querySelectorAll("[data-story-part]").forEach((el) => {
    const on = id != null && el.closest("[data-story]")?.dataset.story === String(id);
    el.style.viewTransitionName = on ? `story-${el.dataset.storyPart}` : "";
  });
}

export function routeCommitted() {
  if (!committed) return;
  nameStory(active);
  committed();
  committed = null;
}

/** Run `navigate` as a view transition; `storyId` is the item whose parts should morph. */
export function transitionTo(navigate, storyId) {
  if (!document.startViewTransition || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return navigate();
  active = storyId;
  nameStory(storyId);
  document.startViewTransition(() => new Promise((resolve) => {
    committed = resolve;
    setTimeout(() => committed === resolve && routeCommitted(), 500); // never freeze the screen
    navigate();
  }));
}
