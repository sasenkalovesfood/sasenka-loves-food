#!/usr/bin/env python3
"""Phase 1 parser: turn 63 remaining review.json sources into a working dataset.

- Reads every source folder under _working/sources/food_reviews/
- Skips the 8 already-imported reviews
- Extracts: slug, restaurant, date, handle, photos, hero caption
- Parses the caption for "Pictured" list and inline ratings
- Normalises suburb + cuisine against existing taxonomies where confidently matched;
  otherwise flags for user review
- Writes phase1-dataset.json and phase1-summary.md
"""
import json
import os
import re
from datetime import datetime

BASE = "/sessions/kind-eloquent-meitner/mnt/SLF/sasenka-loves-food/_working/sources/food_reviews"
OUT_DIR = "/sessions/kind-eloquent-meitner/mnt/SLF/sasenka-loves-food/_working"

ALREADY_IMPORTED = {
    "2025-04-20_stilts-dining",
    "2025-04-24_barryparadeph",
    "2025-04-26_thegreen-au",
    "2025-04-30_thefiftysixrestaurant",
    "2025-05-02_naldhamhouse",
    "2025-05-02_penelope-bistro",
    "2025-05-05_HimalayanCafe",
    "2025-05-07_attimi-brisbane",
}

# Existing taxonomy buckets used by the live archive.
EXISTING_CUISINES = {
    "italian-degustation", "nepali", "european-brasserie", "french-bistro",
    "cantonese", "modern-middle-eastern", "creole", "modern-australian",
}
EXISTING_SUBURBS = {
    "paddington", "new-farm", "brisbane-cbd", "james-street", "fortitude-valley",
}

# Brisbane suburbs + hint phrases to recognise in captions.
SUBURB_HINTS = [
    ("brisbane-cbd",        ["brisbane cbd", "cbd of brisbane", "the city", "queen street", "eagle street", "burnett lane", "elizabeth street, brisbane"]),
    ("new-farm",            ["new farm"]),
    ("fortitude-valley",    ["fortitude valley", "the valley", "james street", "wandoo street", "ann street"]),  # james street sits inside fortitude valley on the map; kept separate below
    ("james-street",        ["james street, fortitude valley", "james st, fortitude valley"]),
    ("paddington",          ["paddington"]),
    ("west-end",            ["west end"]),
    ("south-brisbane",      ["south brisbane", "south bank"]),
    ("teneriffe",           ["teneriffe"]),
    ("newstead",            ["newstead", "skyring terrace"]),
    ("spring-hill",         ["spring hill"]),
    ("milton",              ["milton"]),
    ("kangaroo-point",      ["kangaroo point"]),
    ("noosa",               ["noosa"]),
    ("maleny",              ["maleny"]),
    ("hobart",              ["hobart"]),
    ("carlton",             ["carlton, melbourne", "carlton, vic", "lygon street"]),
    ("melbourne",           ["melbourne"]),
    ("singapore",           ["singapore", "clarke quay", "marina bay"]),
    ("colombo",             ["colombo", "sri lanka"]),
    ("delft",               ["delft", "netherlands"]),
    ("auckland",            ["auckland"]),
    ("sydney",              ["sydney"]),
]

# Cuisine hints. Order matters: the first match wins.
CUISINE_HINTS = [
    ("nepali",                   ["nepali", "nepalese", "himalayan", "momo"]),
    ("sri-lankan",               ["sri lankan", "sri-lanka", "kottu", "hoppers"]),
    ("italian-degustation",      ["degustation.*italian", "italian degustation", "attimi"]),
    ("italian",                  ["italian", "pizza", "pasta", "pizzeria", "trattoria", "osteria"]),
    ("french-bistro",            ["french bistro", "bistro fran", "bistrot"]),
    ("french",                   ["french"]),
    ("japanese",                 ["japanese", "sushi", "omakase", "izakaya", "yakitori"]),
    ("chinese-cantonese",        ["cantonese", "dim sum", "yum cha", "char siu"]),
    ("chinese",                  ["chinese", "hand-pulled", "xiaolongbao", "shanghai"]),
    ("korean",                   ["korean", "kbbq", "bibimbap"]),
    ("thai",                     ["thai", "pad "]),
    ("vietnamese",               ["vietnamese", "pho", "banh mi"]),
    ("singaporean",              ["singaporean", "singapore chilli crab", "hawker"]),
    ("middle-eastern",           ["middle eastern", "levantine", "lebanese", "persian", "hummus", "shawarma"]),
    ("greek",                    ["greek", "yamas"]),
    ("spanish-tapas",            ["spanish", "tapas", "jamón", "jamon"]),
    ("mexican",                  ["mexican", "ceviche", "taqueria"]),
    ("peruvian",                 ["peruvian"]),
    ("creole",                   ["creole", "cajun", "new orleans"]),
    ("steakhouse",               ["steakhouse", "dry-aged", "wagyu steak"]),
    ("seafood",                  ["seafood", "chilli crab", "mud crab"]),
    ("modern-australian",        ["modern australian", "contemporary australian", "australian produce"]),
    ("european-brasserie",       ["brasserie", "european"]),
    ("wine-bar",                 ["wine bar", "natural wine"]),
    ("cafe-brunch",              ["brunch", "breakfast", "cafe", "café", "brekky", "muffin"]),
]


def load_review(folder):
    path = os.path.join(BASE, folder, "review.json")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def parse_ratings_from_caption(caption):
    """Look for a 'Rating out of 10:' block inside the caption and return a
    dict with the five scores, or None if not found / incomplete."""
    if not caption:
        return None
    # Accept 'Rating', 'Ratings', 'Rating out of 10', 'Ratings (out of 10):', etc.
    m = re.search(
        r"Rating[s]?\s*(?:\(?out of\s*10\)?)?\s*:?\s*\n(.*?)(?:\n\s*\n|\n#|\Z)",
        caption, re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return None
    block = m.group(1)
    out = {}
    # Allow 'Die', 'Die happy', 'Would I die happy', etc. for the fifth score.
    key_patterns = [
        ("comfort", r"comfort"),
        ("soul", r"soul"),
        ("mastery", r"mastery"),
        ("taste", r"taste"),
        ("would_i_die_happy", r"(?:would\s*i\s*)?die(?:\s*happy)?"),
    ]
    for norm, pat_key in key_patterns:
        pat = rf"{pat_key}\s*[:=\-]?\s*([0-9]+(?:\.[0-9]+)?)"
        mm = re.search(pat, block, re.IGNORECASE)
        if mm:
            out[norm] = float(mm.group(1))
    if len(out) == 5:
        return out
    return None


def parse_star_ratings(caption):
    """Catch the secondary ⭐ rating scheme some posts use: Food/Vibe/Service."""
    if not caption or "⭐" not in caption:
        return None
    out = {}
    for key, norm in [("food", "food"), ("vibe", "vibe"), ("service", "service"),
                      ("ambience", "ambience"), ("value", "value")]:
        m = re.search(rf"{key}\s*:\s*(⭐+)", caption, re.IGNORECASE)
        if m:
            out[norm] = len(m.group(1))
    return out or None


def parse_pictured_list(caption):
    """Find the 'Pictured 📸:' block and return an ordered list of captions."""
    if not caption:
        return []
    m = re.search(r"Pictured[^:]*:(.*?)(?:\n\s*\n|Rating|\Z)",
                  caption, re.IGNORECASE | re.DOTALL)
    if not m:
        return []
    block = m.group(1)
    items = []
    for line in block.splitlines():
        line = line.strip().lstrip("\t").strip()
        # Lines look like "1. Prawn toast" or "01. Item"
        mm = re.match(r"^\d+\.\s*(.+)$", line)
        if mm:
            items.append(mm.group(1).strip())
    return items


def first_paragraph(caption):
    if not caption:
        return ""
    for p in caption.split("\n\n"):
        p = p.strip()
        if p:
            return p
    return ""


def infer_suburb(caption, handle, restaurant):
    hay = " ".join([caption or "", handle or "", restaurant or ""]).lower()
    for bucket, phrases in SUBURB_HINTS:
        for ph in phrases:
            if ph in hay:
                return bucket
    return None


def infer_cuisine(caption, hashtags, restaurant):
    hay = " ".join([
        caption or "",
        " ".join(hashtags or []),
        restaurant or "",
    ]).lower()
    for bucket, phrases in CUISINE_HINTS:
        for ph in phrases:
            if re.search(ph, hay):
                return bucket
    return None


def slugify_restaurant(folder, restaurant):
    """Use the date + a clean slug. The folder name is already in the right shape."""
    return folder


def build_standfirst_themes(caption, pictured):
    """Pull one standfirst-style sentence from the source caption. We do not
    invent: we lift a single sentence that captures the theme, with a light
    edit for tone. If nothing fits, return an empty string and flag."""
    if not caption:
        return ""
    # Prefer the final summary line near "Pictured" or just before it.
    para = first_paragraph(caption)
    # Strip trailing hashtags and the "Rating" block.
    sentences = re.split(r"(?<=[.!?])\s+", para)
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        # Avoid sentences that are just a venue handle or only hashtags.
        if s.startswith("#") or len(s) < 20:
            continue
        return s
    return sentences[0].strip() if sentences else ""


def title_case_restaurant(raw, folder):
    """Clean up restaurant names that Meta exported as lowercase handles."""
    if raw:
        return raw.strip()
    # Fall back to folder-derived name
    tail = folder.split("_", 1)[1] if "_" in folder else folder
    return tail.replace("-", " ").title()


def strip_caption_boilerplate(caption):
    """Return caption with the Pictured block, Rating block, and hashtag block removed."""
    if not caption:
        return ""
    s = caption
    s = re.split(r"\n\s*Pictured", s, maxsplit=1)[0]
    s = re.split(r"\n\s*Rating", s, maxsplit=1)[0]
    s = re.split(r"\n\s*#", s, maxsplit=1)[0]
    return s.strip()


def main():
    folders = sorted(
        f for f in os.listdir(BASE)
        if os.path.isdir(os.path.join(BASE, f))
    )
    new_cuisines = set()
    new_suburbs = set()

    out_records = []
    for folder in folders:
        if folder in ALREADY_IMPORTED:
            continue
        j = load_review(folder)
        caption = j.get("caption") or ""
        pictured = parse_pictured_list(caption)

        # Ratings: prefer JSON-native, fall back to caption-parsed, then stars.
        ratings = j.get("ratings") or {}
        star_ratings = parse_star_ratings(caption)
        if not ratings or ratings.get("taste") is None:
            parsed = parse_ratings_from_caption(caption)
            if parsed:
                ratings = parsed
                ratings_source = "caption-parsed"
            elif star_ratings:
                ratings = None
                ratings_source = "stars-only"
            else:
                ratings = None
                ratings_source = "missing"
        else:
            ratings_source = "json-native"

        suburb_bucket = infer_suburb(caption, j.get("handle"), j.get("restaurant"))
        cuisine_bucket = infer_cuisine(caption, j.get("hashtags"), j.get("restaurant"))

        if cuisine_bucket and cuisine_bucket not in EXISTING_CUISINES:
            new_cuisines.add(cuisine_bucket)
        if suburb_bucket and suburb_bucket not in EXISTING_SUBURBS:
            new_suburbs.add(suburb_bucket)

        media = j.get("media_files") or []
        # Only include photo files (no video) in the gallery photo list.
        photos = [m["filename"] for m in media if not m.get("is_video")]
        hero_photo = photos[0] if photos else None

        # Build per-photo captions: pair 'pictured' entries with photo order.
        photo_captions = []
        if pictured:
            for idx, m in enumerate(media):
                order = m.get("order", idx + 1)
                cap = pictured[order - 1] if 0 <= order - 1 < len(pictured) else ""
                photo_captions.append({
                    "order": order,
                    "filename": m["filename"],
                    "is_video": bool(m.get("is_video")),
                    "caption": cap,
                })
        else:
            for idx, m in enumerate(media):
                photo_captions.append({
                    "order": m.get("order", idx + 1),
                    "filename": m["filename"],
                    "is_video": bool(m.get("is_video")),
                    "caption": "",
                })

        hero_caption = photo_captions[0]["caption"] if photo_captions else ""
        standfirst_seed = build_standfirst_themes(caption, pictured)

        flags = []
        if not j.get("restaurant"):
            flags.append("missing-restaurant-name")
        if not suburb_bucket:
            flags.append("suburb-unresolved")
        if not cuisine_bucket:
            flags.append("cuisine-unresolved")
        if ratings_source == "missing":
            flags.append("ratings-missing")
        if not pictured:
            flags.append("no-pictured-list")
        if any(m.get("is_video") for m in media):
            flags.append("contains-video")
        if any(m["filename"].lower().endswith(".heic") for m in media):
            flags.append("heic-photos")

        record = {
            "slug": folder,
            "order": j.get("review_number"),
            "date_iso": j.get("date_iso"),
            "date_display": j.get("date"),
            "restaurant_name": title_case_restaurant(j.get("restaurant"), folder),
            "instagram_handle": j.get("handle") or "",
            "all_mentions": j.get("all_mentions") or [],
            "hashtags": j.get("hashtags") or [],
            "suburb": {
                "bucket": suburb_bucket,
                "is_existing": (suburb_bucket in EXISTING_SUBURBS) if suburb_bucket else False,
            },
            "cuisine": {
                "bucket": cuisine_bucket,
                "is_existing": (cuisine_bucket in EXISTING_CUISINES) if cuisine_bucket else False,
            },
            "ratings": ratings,
            "ratings_source": ratings_source,
            "star_ratings": star_ratings,
            "photo_count": j.get("photo_count", 0),
            "video_count": j.get("video_count", 0),
            "hero_photo": hero_photo,
            "photos": photo_captions,
            "proposed_hero_caption": hero_caption,
            "standfirst_seed_from_source": standfirst_seed,
            "caption_clean": strip_caption_boilerplate(caption),
            "caption_raw": caption,
            "flags": flags,
        }
        out_records.append(record)

    # Sort newest first (matches site convention).
    out_records.sort(key=lambda r: r["date_iso"] or "", reverse=True)

    dataset = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "source_folder": BASE,
        "already_imported_slugs": sorted(ALREADY_IMPORTED),
        "existing_cuisine_buckets": sorted(EXISTING_CUISINES),
        "existing_suburb_buckets": sorted(EXISTING_SUBURBS),
        "proposed_new_cuisine_buckets": sorted(new_cuisines),
        "proposed_new_suburb_buckets": sorted(new_suburbs),
        "review_count": len(out_records),
        "reviews": out_records,
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "phase1-dataset.json"), "w", encoding="utf-8") as fh:
        json.dump(dataset, fh, indent=2, ensure_ascii=False)

    # Summary markdown
    lines = []
    lines.append("# Phase 1 parse summary")
    lines.append("")
    lines.append(f"- Total reviews parsed: **{len(out_records)}**")
    lines.append(f"- Already imported, skipped: **{len(ALREADY_IMPORTED)}**")
    lines.append(f"- Generated: {dataset['generated_at']}")
    lines.append("")
    lines.append("## Ratings provenance")
    by_source = {}
    for r in out_records:
        by_source[r["ratings_source"]] = by_source.get(r["ratings_source"], 0) + 1
    for k in ("json-native", "caption-parsed", "stars-only", "missing"):
        lines.append(f"- {k}: {by_source.get(k, 0)}")
    lines.append("")
    lines.append("## New taxonomy buckets proposed")
    lines.append("")
    lines.append("### New cuisine buckets")
    if new_cuisines:
        for c in sorted(new_cuisines):
            lines.append(f"- `{c}`")
    else:
        lines.append("_(none)_")
    lines.append("")
    lines.append("### New suburb buckets")
    if new_suburbs:
        for s in sorted(new_suburbs):
            lines.append(f"- `{s}`")
    else:
        lines.append("_(none)_")
    lines.append("")
    lines.append("## Review-by-review flags")
    lines.append("")
    lines.append("| Date | Slug | Restaurant | Cuisine | Suburb | Ratings | Flags |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for r in out_records:
        date = (r["date_iso"] or "")[:10]
        cuisine = r["cuisine"]["bucket"] or "_unresolved_"
        suburb = r["suburb"]["bucket"] or "_unresolved_"
        rs = r["ratings_source"]
        flags = ", ".join(r["flags"]) or "-"
        lines.append(f"| {date} | `{r['slug']}` | {r['restaurant_name']} | `{cuisine}` | `{suburb}` | {rs} | {flags} |")
    lines.append("")
    lines.append("## Reviews needing score proposals (no source ratings)")
    lines.append("")
    missing = [r for r in out_records if r["ratings_source"] == "missing"]
    if missing:
        for r in missing:
            lines.append(f"- `{r['slug']}` ({r['restaurant_name']})")
    else:
        lines.append("_(none)_")
    lines.append("")

    with open(os.path.join(OUT_DIR, "phase1-summary.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    print(f"Wrote {len(out_records)} records to phase1-dataset.json")
    print(f"Ratings: {by_source}")
    print(f"New cuisines: {sorted(new_cuisines)}")
    print(f"New suburbs: {sorted(new_suburbs)}")


if __name__ == "__main__":
    main()
