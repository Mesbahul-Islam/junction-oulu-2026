"""Community vote desk: post the shortlist members vote on ("What should we cover next?").

After the news editor's pick, the best stories it did *not* cover go on the shortlist.
Members vote in the app; the next run adds those votes to Jev's score (``news_editor.rank``).
Stories that were picked are marked covered (members see their vote turned into a story);
stories that left the wire desk's window or were written up otherwise drop off. Titles are
machine-translated, one model call per language, so every member can read what they vote on.
"""

from __future__ import annotations

from apps.common.choices import SAMI_LANGUAGES

from ..graph.text import LANGUAGE_LABELS, jaccard, language_problem
from ..models import CoverageCandidate
from . import ai

SHORTLIST_SIZE = 10


def translate_titles(titles: dict[int, str], languages: list[str]) -> dict[int, dict[str, str]]:
    """{candidate id: {lang: title}} for every language the model got right."""
    out: dict[int, dict[str, str]] = {pk: {} for pk in titles}
    if not titles:
        return out
    keys = [str(pk) for pk in titles]
    source = {str(pk): t for pk, t in titles.items()}
    for lang in languages:
        data, _problem = ai.ask_json(
            "translator",
            f"Translate each of these Finnish news headlines into {LANGUAGE_LABELS.get(lang, lang)}. Keep names "
            f"and numbers. Return the same keys.\n\n{source}",
            keys,
        )
        for key, text in (data or {}).items():
            text = str(text).strip()
            # Headlines are short, so also refuse an "translation" that is still the Finnish.
            if key in source and text and not language_problem(text, lang) and jaccard(text, source[key]) < 0.5:
                out[int(key)][lang] = text[:300]
    return out


def publish(run, ranked: list[dict], picked: list, languages: list[str]) -> dict:
    """Update the community's shortlist after a run. Returns a report for the dashboard."""
    community = run.community
    picked_ids = {story.source_document_id: story for story in picked}
    # What members voted for and the newsroom now covers.
    covered = 0
    for cand in CoverageCandidate.objects.filter(community=community, status="open", source_document_id__in=picked_ids):
        cand.status, cand.covered_by = CoverageCandidate.Status.COVERED, picked_ids[cand.source_document_id]
        cand.save(update_fields=["status", "covered_by", "updated_at"])
        covered += 1

    still_candidates = {r["doc"].pk: r for r in ranked}
    best = [r for r in ranked if r["doc"].pk not in picked_ids][:SHORTLIST_SIZE]
    keep = {r["doc"].pk for r in best}
    # Stories members already voted for stay on the list while they are still candidates.
    keep |= set(CoverageCandidate.objects.filter(community=community, status="open", votes__isnull=False,
                                                 source_document_id__in=still_candidates).values_list("source_document_id", flat=True))
    dropped = CoverageCandidate.objects.filter(community=community, status="open").exclude(source_document_id__in=keep).update(
        status=CoverageCandidate.Status.DROPPED)

    langs = [lang for lang in languages if lang != "fi" and lang not in SAMI_LANGUAGES]
    new_titles = {}
    for doc_id in keep:
        r = still_candidates[doc_id]
        cand, created = CoverageCandidate.objects.update_or_create(
            community=community, source_document=r["doc"],
            defaults={"status": CoverageCandidate.Status.OPEN, "jev_score": r["jev"], "ranked_by": r["ranked_by"],
                      "reasons": [w for w in r["reasons"] if "voted" not in w]},
        )
        if created or set(langs) - set(cand.titles or {}):  # new, or a reader language still missing
            new_titles[cand.pk] = r["doc"].title
    for pk, titles in translate_titles(new_titles, langs).items():
        CoverageCandidate.objects.filter(pk=pk).update(titles={"fi": new_titles[pk], **titles})
    return {"open": len(keep), "added": len(new_titles), "covered": covered, "dropped": dropped,
            "title_languages": langs}
