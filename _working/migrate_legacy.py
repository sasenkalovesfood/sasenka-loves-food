"""One-time migration: build data/legacy-index.json from the current site HTML.

This snapshot preserves every hand-tuned detail of the 63 legacy reviews
(blurbs, photos, chip ordering) so that the build script can rebuild the
archive and homepage around them without losing the tuning.

For each of the 63 reviews it captures:

    * Machine fields: slug, date, cuisine, suburb, scores, IG handle.
    * The full archive grid-card HTML and list-row HTML, verbatim from
      /reviews-archive.html, so the archive can be rebuilt with zero
      visual change.
    * If the review appears on the current homepage, its homepage blurb
      and thumbnail choices, so those hand-written blurbs are preserved
      even when a new review bumps the review down the grid.
    * The filter-chip row HTML from the archive, verbatim, so the
      curated chip ordering is preserved.

The script writes data/legacy-index.json. Existing HTML files are never
modified.

Usage:
    python3 _working/migrate_legacy.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / "reviews-archive.html"
INDEX = ROOT / "index.html"
REVIEWS_DIR = ROOT / "reviews"
OUT = ROOT / "data" / "legacy-index.json"


# ---- Regexes ---------------------------------------------------------------

GRID_CARD_RE = re.compile(
    r'<a class="review-card archive-card" href="(?P<href>reviews/[^"]+)"\s*'
    r'data-cuisine="(?P<cuisine>[^"]+)" data-suburb="(?P<suburb>[^"]+)"\s*'
    r'data-date="(?P<date>[^"]+)"\s*'
    r'data-comfort="(?P<comfort>[^"]+)" data-soul="(?P<soul>[^"]+)"\s+'
    r'data-mastery="(?P<mastery>[^"]+)" data-taste="(?P<taste>[^"]+)" data-die="(?P<die>[^"]+)">'
    r'(?P<inner>.*?)</a>',
    re.DOTALL,
)

LIST_ROW_RE = re.compile(
    r'<a class="archive-row archive-card" href="(?P<href>reviews/[^"]+)"'
    r'(?P<rest>.*?)</a>',
    re.DOTALL,
)

HOMEPAGE_FEATURED_RE = re.compile(
    r'<a class="feature-review" href="(?P<href>reviews/[^"]+)">\s*'
    r'<div class="photo" style="background-image: url\(\'(?P<thumb>[^\']+)\'\);"></div>\s*'
    r'<div class="body">\s*'
    r'<div class="meta">(?P<meta>[^<]+)</div>\s*'
    r'<h2>(?P<name>[^<]+)</h2>\s*'
    r'<p class="blurb">(?P<blurb>[^<]+)</p>',
    re.DOTALL,
)

HOMEPAGE_CARD_RE = re.compile(
    r'<a class="review-card" href="(?P<href>reviews/[^"]+)">\s*'
    r'<div class="thumb" style="background-image: url\(\'(?P<thumb>[^\']+)\'\);"></div>\s*'
    r'<div class="body">\s*'
    r'<div class="meta">(?P<meta>.*?)</div>\s*'
    r'<h3>(?P<name>[^<]+)</h3>\s*'
    r'<p class="blurb">(?P<blurb>[^<]+)</p>',
    re.DOTALL,
)

CUISINE_ROW_RE = re.compile(
    r'(<div class="chip-row" role="group" aria-label="Cuisine">.*?</div>)',
    re.DOTALL,
)
SUBURB_ROW_RE = re.compile(
    r'(<div class="chip-row" role="group" aria-label="Suburb">.*?</div>)',
    re.DOTALL,
)
CHIP_FILTER_RE = re.compile(r'data-filter="([^"]+)"')

IG_FACT_RE = re.compile(
    r'<div class="fact"><span class="label">Instagram</span>'
    r'<a href="https://instagram.com/([^"/?]+)"'
)

META_DESC_RE = re.compile(r'<meta name="description" content="([^"]+)"')

HERO_RE = re.compile(
    r'<div class="review-hero">\s*'
    r'<div class="photo"[^>]*style="background-image:url\(\'\.\./([^\']+)\'\);?"',
    re.DOTALL,
)


def parse_meta(meta_html: str) -> tuple[str, str]:
    # "Newstead &middot; Nepali / Himalayan" -> ("Newstead", "Nepali / Himalayan")
    decoded = meta_html.replace("&middot;", "\u00b7").replace("&amp;", "&")
    if "\u00b7" in decoded:
        parts = [p.strip() for p in decoded.split("\u00b7", 1)]
        return parts[0], parts[1]
    return decoded.strip(), ""


def parse_archive(html: str) -> dict[str, dict]:
    """Return dict keyed by slug with archive grid + list + machine fields."""
    entries: dict[str, dict] = {}

    for m in GRID_CARD_RE.finditer(html):
        slug = Path(m.group("href")).stem
        entries.setdefault(slug, {})
        entries[slug].update(
            {
                "slug": slug,
                "href": m.group("href"),
                "date": m.group("date"),
                "cuisine_slug": m.group("cuisine"),
                "suburb_slug": m.group("suburb"),
                "scores": {
                    "comfort": float(m.group("comfort")),
                    "soul": float(m.group("soul")),
                    "mastery": float(m.group("mastery")),
                    "taste": float(m.group("taste")),
                    "die_happy": float(m.group("die")),
                },
                "archive_grid_html": m.group(0),  # full <a>...</a>
            }
        )

        # Parse restaurant name, blurb, suburb_display, cuisine_display from the inner text.
        inner = m.group("inner")
        name_m = re.search(r'<h3>([^<]+)</h3>', inner)
        blurb_m = re.search(r'<p class="blurb">([^<]+)</p>', inner)
        meta_m = re.search(r'<div class="meta"><span>([^<]+)</span>', inner)
        thumb_m = re.search(r"background-image: url\('([^']+)'\);", inner)
        if name_m:
            entries[slug]["restaurant_name"] = name_m.group(1)
        if blurb_m:
            entries[slug]["blurb"] = blurb_m.group(1)
        if meta_m:
            suburb_d, cuisine_d = parse_meta(meta_m.group(1))
            entries[slug]["suburb_display"] = suburb_d
            entries[slug]["cuisine_display"] = cuisine_d
        if thumb_m:
            entries[slug]["thumb"] = thumb_m.group(1)

    for m in LIST_ROW_RE.finditer(html):
        slug = Path(m.group("href")).stem
        entries.setdefault(slug, {})
        entries[slug]["archive_list_html"] = m.group(0)

    return entries


def parse_homepage_overrides(html: str) -> dict[str, dict]:
    overrides: dict[str, dict] = {}
    m = HOMEPAGE_FEATURED_RE.search(html)
    if m:
        slug = Path(m.group("href")).stem
        overrides[slug] = {
            "homepage_thumb": m.group("thumb"),
            "homepage_blurb": m.group("blurb"),
            "homepage_position": "featured",
        }
    for m in HOMEPAGE_CARD_RE.finditer(html):
        slug = Path(m.group("href")).stem
        overrides[slug] = {
            "homepage_thumb": m.group("thumb"),
            "homepage_blurb": m.group("blurb"),
            "homepage_position": "grid",
        }
    return overrides


def parse_filter_chip_rows(html: str) -> dict[str, dict]:
    cuisine_row = CUISINE_ROW_RE.search(html)
    suburb_row = SUBURB_ROW_RE.search(html)
    cuisine_html = cuisine_row.group(1) if cuisine_row else ""
    suburb_html = suburb_row.group(1) if suburb_row else ""
    return {
        "cuisine_html": cuisine_html,
        "cuisine_filters": CHIP_FILTER_RE.findall(cuisine_html),
        "suburb_html": suburb_html,
        "suburb_filters": CHIP_FILTER_RE.findall(suburb_html),
    }


def enrich_from_review(slug: str, entry: dict) -> None:
    review_path = REVIEWS_DIR / f"{slug}.html"
    if not review_path.exists():
        return
    try:
        html = review_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        html = review_path.read_text(encoding="utf-8", errors="replace")

    ig = IG_FACT_RE.search(html)
    if ig:
        entry["instagram_handle"] = ig.group(1).strip()

    md = META_DESC_RE.search(html)
    if md:
        entry["meta_description"] = md.group(1)

    hero = HERO_RE.search(html)
    if hero:
        entry["hero_photo"] = hero.group(1)


def main() -> None:
    archive_html = ARCHIVE.read_text(encoding="utf-8")
    index_html = INDEX.read_text(encoding="utf-8")

    entries = parse_archive(archive_html)

    # Merge homepage overrides
    for slug, over in parse_homepage_overrides(index_html).items():
        if slug in entries:
            entries[slug].update(over)
        else:
            entries[slug] = {"slug": slug, **over}

    # Enrich from review HTML
    for slug, entry in entries.items():
        enrich_from_review(slug, entry)

    ordered = sorted(entries.values(), key=lambda r: r.get("date", ""), reverse=True)
    chips = parse_filter_chip_rows(archive_html)

    payload = {
        "generated_notes": (
            "Snapshot of the 63 hand-edited review pages, verbatim archive cards "
            "and the current homepage blurb/thumb tuning. The build script treats "
            "these as read-only and composes them with any new CMS reviews. "
            "Regenerate with python3 _working/migrate_legacy.py if hand-edits change."
        ),
        "count": len(ordered),
        "filter_chips": chips,
        "reviews": ordered,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} with {len(ordered)} entries")

    # Sanity checks
    missing_grid = [r["slug"] for r in ordered if "archive_grid_html" not in r]
    missing_list = [r["slug"] for r in ordered if "archive_list_html" not in r]
    hp = [r["slug"] for r in ordered if "homepage_blurb" in r]
    if missing_grid:
        print(f"  warning: {len(missing_grid)} entries missing archive grid HTML: {missing_grid[:3]}")
    if missing_list:
        print(f"  warning: {len(missing_list)} entries missing archive list HTML: {missing_list[:3]}")
    print(f"  captured {len(hp)} homepage overrides")
    print(f"  captured {len(chips['cuisine_filters'])} cuisine chips, {len(chips['suburb_filters'])} suburb chips")


if __name__ == "__main__":
    main()
