#!/usr/bin/env python3
"""Merge phase1-dataset.json with the phase2 edits JSON to produce
phase2-final.json, the authoritative dataset for Phase 3.

- Applies edits on top of the parse output
- Normalises cuisine and suburb bucket names (lowercase, hyphenated)
- Honours include/notes/exclude flags
- Surfaces edge cases in a merge-notes file
"""
import json
import os
import re
import shutil

WORK = "/sessions/kind-eloquent-meitner/mnt/SLF/sasenka-loves-food/_working"
DATASET = os.path.join(WORK, "phase1-dataset.json")
EDITS = "/sessions/kind-eloquent-meitner/mnt/uploads/phase2-edits-2026-04-20T08-01-10.json"
OUT = os.path.join(WORK, "phase2-final.json")
NOTES = os.path.join(WORK, "phase2-merge-notes.md")


def normalise_bucket(v):
    if not v:
        return ""
    s = str(v).strip().lower()
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"[^a-z0-9\-]", "", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


# Corrections for clear typos.
BUCKET_OVERRIDES = {
    "woo-fired": "wood-fired",
}


def fix_bucket(v):
    n = normalise_bucket(v)
    return BUCKET_OVERRIDES.get(n, n)


def main():
    with open(DATASET, "r", encoding="utf-8") as fh:
        d = json.load(fh)
    with open(EDITS, "r", encoding="utf-8") as fh:
        e = json.load(fh)

    reviews_by_slug = {r["slug"]: r for r in d["reviews"]}
    edits = e.get("edits", {})

    notes = []
    merged = []
    excluded = []
    not_reviewed = []
    all_cuisines = set()
    all_suburbs = set()

    for slug, base in reviews_by_slug.items():
        ed = edits.get(slug) or {}

        # Status: default to include if reviewed, flag if neither reviewed nor
        # exclude-marked.
        include_status = ed.get("include_status", "include")
        reviewed = bool(ed.get("reviewed"))

        if include_status == "exclude":
            excluded.append({
                "slug": slug,
                "reason": (
                    "User marked exclude" if reviewed or include_status == "exclude"
                    else "User marked exclude"
                ),
                "restaurant_name": base.get("restaurant_name"),
            })
            continue

        if not reviewed and not ed:
            not_reviewed.append(slug)

        # Apply metadata edits
        restaurant_name = ed.get("restaurant_name") or base.get("restaurant_name") or ""
        handle = ed.get("instagram_handle") or base.get("instagram_handle") or ""

        cuisine_raw = ed.get("cuisine_bucket") or base["cuisine"]["bucket"] or ""
        suburb_raw = ed.get("suburb_bucket") or base["suburb"]["bucket"] or ""
        cuisine = fix_bucket(cuisine_raw)
        suburb = fix_bucket(suburb_raw)

        if cuisine_raw and cuisine != normalise_bucket(cuisine_raw):
            notes.append(f"- `{slug}`: cuisine corrected `{cuisine_raw}` -> `{cuisine}` (typo / normalisation)")
        if cuisine != cuisine_raw and cuisine_raw.lower() != cuisine:
            # Note only genuine changes beyond case/hyphen-normalisation.
            pass

        all_cuisines.add(cuisine) if cuisine else None
        all_suburbs.add(suburb) if suburb else None

        # Scores: prefer edits > parse output
        scores = ed.get("scores") or base.get("ratings") or {}
        # Normalise score keys + cast to float
        clean_scores = {}
        for k in ["comfort", "soul", "mastery", "taste", "would_i_die_happy"]:
            v = scores.get(k)
            if v is None or v == "":
                continue
            try:
                clean_scores[k] = float(v)
            except (TypeError, ValueError):
                pass

        # Photos: start from base.photos, apply per-photo caption overrides,
        # and apply hero_photo choice.
        photos = []
        cap_override = ed.get("photo_captions") or {}
        for p in base.get("photos") or []:
            order = str(p.get("order"))
            cap = cap_override.get(order, p.get("caption") or "")
            photos.append({
                "order": p.get("order"),
                "filename": p["filename"],
                "is_video": bool(p.get("is_video")),
                "is_heic": p["filename"].lower().endswith(".heic"),
                "caption": cap.strip() if cap else "",
            })

        hero_photo = ed.get("hero_photo")
        if not hero_photo:
            # Default: first non-video, non-HEIC
            for p in photos:
                if not p["is_video"] and not p["is_heic"]:
                    hero_photo = p["filename"]
                    break
        if not hero_photo:
            # Fallback: first photo of any kind
            for p in photos:
                if not p["is_video"]:
                    hero_photo = p["filename"]
                    break

        hero_caption = ed.get("hero_caption") or ""
        if not hero_caption:
            # Fall back to the caption for the hero photo
            for p in photos:
                if p["filename"] == hero_photo:
                    hero_caption = p["caption"]
                    break

        standfirst = ed.get("standfirst") or base.get("standfirst_seed_from_source") or ""
        notes_text = ed.get("notes") or ""

        merged.append({
            "slug": slug,
            "order": base.get("order"),
            "date_iso": base.get("date_iso"),
            "restaurant_name": restaurant_name,
            "instagram_handle": handle,
            "suburb_bucket": suburb,
            "cuisine_bucket": cuisine,
            "scores": clean_scores,
            "scores_complete": len(clean_scores) == 5,
            "ratings_source_original": base.get("ratings_source"),
            "hero_photo": hero_photo,
            "hero_caption": hero_caption,
            "standfirst": standfirst,
            "photos": photos,
            "caption_source": base.get("caption_raw") or "",
            "hashtags": base.get("hashtags") or [],
            "all_mentions": base.get("all_mentions") or [],
            "include_status": include_status,
            "private_notes": notes_text,
        })

    # Sort newest first
    merged.sort(key=lambda r: r["date_iso"] or "", reverse=True)

    # Quality checks
    qc = {
        "missing_scores": [r["slug"] for r in merged if not r["scores_complete"]],
        "missing_cuisine": [r["slug"] for r in merged if not r["cuisine_bucket"]],
        "missing_suburb": [r["slug"] for r in merged if not r["suburb_bucket"]],
        "missing_name": [r["slug"] for r in merged if not r["restaurant_name"]],
        "hero_is_heic": [r["slug"] for r in merged if r["hero_photo"] and r["hero_photo"].lower().endswith(".heic")],
        "not_reviewed_by_user": not_reviewed,
    }

    final = {
        "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "total_parsed": len(reviews_by_slug),
        "included_count": len(merged),
        "excluded_count": len(excluded),
        "excluded": excluded,
        "cuisines_in_use": sorted(all_cuisines),
        "suburbs_in_use": sorted(all_suburbs),
        "quality_checks": qc,
        "merge_notes": notes,
        "reviews": merged,
    }

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(final, fh, indent=2, ensure_ascii=False)

    # Markdown notes
    md = []
    md.append("# Phase 2 merge, notes for review")
    md.append("")
    md.append(f"- **Included in live archive:** {len(merged)}")
    md.append(f"- **Excluded (user marked):** {len(excluded)}")
    md.append(f"- **Parsed total:** {len(reviews_by_slug)}")
    md.append("")
    md.append("## Excluded reviews")
    md.append("")
    for x in excluded:
        md.append(f"- `{x['slug']}` ({x['restaurant_name']})")
    md.append("")
    md.append("## Cuisine buckets now in use (normalised)")
    md.append("")
    for c in sorted(all_cuisines):
        count = sum(1 for r in merged if r["cuisine_bucket"] == c)
        md.append(f"- `{c}` × {count}")
    md.append("")
    md.append("## Suburb buckets now in use (normalised)")
    md.append("")
    for s in sorted(all_suburbs):
        count = sum(1 for r in merged if r["suburb_bucket"] == s)
        md.append(f"- `{s}` × {count}")
    md.append("")
    md.append("## Corrections and normalisations applied")
    md.append("")
    if notes:
        md.extend(notes)
    else:
        md.append("_(none)_")
    md.append("")
    md.append("## Open questions for Sasenka")
    md.append("")
    if qc["not_reviewed_by_user"]:
        md.append("### Reviews not touched in staging pass")
        md.append("")
        for slug in qc["not_reviewed_by_user"]:
            md.append(f"- `{slug}` -> included by default")
        md.append("")
    if qc["missing_scores"]:
        md.append("### Reviews still missing one or more scores")
        md.append("")
        for slug in qc["missing_scores"]:
            md.append(f"- `{slug}`")
        md.append("")
    if qc["missing_cuisine"]:
        md.append("### Reviews still missing cuisine")
        md.append("")
        for slug in qc["missing_cuisine"]:
            md.append(f"- `{slug}`")
        md.append("")
    if qc["missing_suburb"]:
        md.append("### Reviews still missing suburb")
        md.append("")
        for slug in qc["missing_suburb"]:
            md.append(f"- `{slug}`")
        md.append("")
    if qc["missing_name"]:
        md.append("### Reviews still missing restaurant name")
        md.append("")
        for slug in qc["missing_name"]:
            md.append(f"- `{slug}`")
        md.append("")
    if qc["hero_is_heic"]:
        md.append("### Reviews whose hero photo is HEIC (needs conversion before publish)")
        md.append("")
        for slug in qc["hero_is_heic"]:
            md.append(f"- `{slug}`")
        md.append("")

    with open(NOTES, "w", encoding="utf-8") as fh:
        fh.write("\n".join(md))

    # Print summary
    print(f"Wrote: {OUT}")
    print(f"Included: {len(merged)}, Excluded: {len(excluded)}")
    print(f"Cuisines in use ({len(all_cuisines)}): {sorted(all_cuisines)}")
    print(f"Suburbs in use ({len(all_suburbs)}): {sorted(all_suburbs)}")
    print(f"QC: {qc}")


if __name__ == "__main__":
    main()
