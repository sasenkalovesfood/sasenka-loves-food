"""Build script for Sasenka Loves Food.

Runs on every Netlify deploy (configured in netlify.toml). It stitches
together two sources of review metadata:

  1. data/legacy-index.json
     A snapshot of the 63 hand-edited reviews. For each one it holds the
     archive grid/list HTML verbatim, plus any hand-tuned homepage blurb
     and thumbnail. This script treats legacy HTML files as read-only.

  2. data/reviews/*.json
     Full content for any review written through the Decap CMS. For each
     published entry the script regenerates /reviews/<slug>.html from
     scratch on every build.

Combined, they drive updates to:

  - Homepage featured block and recent-reviews grid.
  - Archive filter chips (cuisine + suburb).
  - Archive month-grouped grid + list views.

The Instagram strip on the homepage is intentionally left alone: Sasenka
curates it by hand.

Replaceable regions are bracketed by HTML comments of the form
<!-- BUILD:NAME --> ... <!-- /BUILD:NAME -->. The script replaces what
sits between those markers and leaves everything else untouched.

Run locally with: python3 build.py
"""

from __future__ import annotations

import html as _html
import json
import re
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent
DATA_LEGACY = ROOT / "data" / "legacy-index.json"
DATA_REVIEWS_DIR = ROOT / "data" / "reviews"
REVIEWS_DIR = ROOT / "reviews"
INDEX_HTML = ROOT / "index.html"
ARCHIVE_HTML = ROOT / "reviews-archive.html"
LINKS_HTML = ROOT / "links.html"

GENERATED_MARKER = "<!-- GENERATED FROM data/reviews/"

HOMEPAGE_GRID_SIZE = 6

MONTH_LABELS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Filter bucket mapping. The CMS lets Sasenka write cuisine/suburb as free
# text so the granular label on each review page stays hers. For the archive
# filter chips we fold each entry into one of the rationalised buckets below.
# An unmapped value falls through as-is (render_filters then appends a new
# chip, which is our signal to extend this map).
CUISINE_BUCKETS = {
    "modern-australian":     "modern-australian",
    "italian":               "italian",
    "italian-degustation":   "italian",
    "chinese":               "chinese",
    "cantonese":             "chinese",
    "japanese":              "japanese",
    "nepali":                "pan-asian",
    "modern-asian":          "pan-asian",
    "korean":                "pan-asian",
    "malaysian":             "pan-asian",
    "singaporean":           "pan-asian",
    "thai":                  "pan-asian",
    "vietnamese":            "pan-asian",
    "sri-lankan":            "sri-lankan",
    "greek":                 "mediterranean",
    "middle-eastern":        "mediterranean",
    "modern-middle-eastern": "mediterranean",
    "mediterranean":         "mediterranean",
    "spanish":               "mediterranean",
    "french":                "french-european",
    "french-bistro":         "french-european",
    "european-brasserie":    "french-european",
    "nordic":                "french-european",
    "european":              "french-european",
    "seafood":               "fire-and-ocean",
    "wood-fired":            "fire-and-ocean",
    "steakhouse":            "steakhouse",
    "creole":                "creole",
}

SUBURB_BUCKETS = {
    "brisbane-cbd":     "brisbane-cbd",
    "fortitude-valley": "fortitude-valley",
    "west-end":         "west-end",
    "james-street":     "james-street-newstead",
    "newstead":         "james-street-newstead",
    "south-brisbane":   "south-brisbane-south-bank",
    "southbank":        "south-brisbane-south-bank",
    "south-bank":       "south-brisbane-south-bank",
    "woolloongabba":    "south-brisbane-south-bank",
    "paddington":       "inner-suburbs",
    "new-farm":         "inner-suburbs",
    "spring-hill":      "inner-suburbs",
    "morningside":      "inner-suburbs",
    "coorparoo":        "inner-suburbs",
    "greenslopes":      "inner-suburbs",
    "red-hill":         "inner-suburbs",
    "bulimba":          "inner-suburbs",
    "teneriffe":        "inner-suburbs",
    "noosa":            "sunshine-coast",
    "maleny":           "sunshine-coast",
    "montville":        "sunshine-coast",
    "hobart":           "australia-elsewhere",
    "melbourne":        "australia-elsewhere",
    "carlton":          "australia-elsewhere",
    "ballina":          "australia-elsewhere",
    "sydney":           "australia-elsewhere",
    "singapore":        "overseas",
    "delft":            "overseas",
    "rhodes":           "overseas",
}


def bucket_cuisine(raw: str) -> str:
    k = kebab(raw)
    return CUISINE_BUCKETS.get(k, k)


def bucket_suburb(raw: str) -> str:
    k = kebab(raw)
    return SUBURB_BUCKETS.get(k, k)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def kebab(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def esc(text: str) -> str:
    return _html.escape(text or "", quote=True)


def fmt_score(n) -> str:
    try:
        return f"{float(n):.1f}"
    except (TypeError, ValueError):
        return "0.0"


def ordinal_date(iso_date: str) -> str:
    y, m, d = iso_date.split("-")
    return f"{int(d)} {MONTH_LABELS[int(m) - 1]} {y}"


def short_date(iso_date: str) -> str:
    y, m, d = iso_date.split("-")
    return f"{int(d)} {MONTH_ABBR[int(m) - 1]} {y}"


def month_label(iso_date: str) -> str:
    y, m, _ = iso_date.split("-")
    return f"{MONTH_LABELS[int(m) - 1]} {y}"


def month_year_short(iso_date: str) -> str:
    y, m, _ = iso_date.split("-")
    return f"{MONTH_ABBR[int(m) - 1]} {y}"


def month_key(iso_date: str) -> str:
    return iso_date[:7]


def replace_marker(source: str, name: str, replacement: str) -> str:
    pattern = re.compile(
        rf"(<!-- BUILD:{re.escape(name)} -->)(.*?)(<!-- /BUILD:{re.escape(name)} -->)",
        re.DOTALL,
    )
    if not pattern.search(source):
        raise RuntimeError(f"Marker BUILD:{name} not found")
    return pattern.sub(lambda m: f"{m.group(1)}\n{replacement}\n      {m.group(3)}", source, count=1)


# ----------------------------------------------------------------------------
# Minimal markdown -> HTML for the CMS body field
# ----------------------------------------------------------------------------

_INLINE_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_INLINE_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_INLINE_ITALIC = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")


def _inline(text: str) -> str:
    out = esc(text)
    out = _INLINE_LINK.sub(
        lambda m: f'<a href="{m.group(2)}" target="_blank" rel="noopener">{m.group(1)}</a>',
        out,
    )
    out = _INLINE_BOLD.sub(r"<strong>\1</strong>", out)
    out = _INLINE_ITALIC.sub(r"<em>\1</em>", out)
    return out


def md_to_html(body: str) -> str:
    if not body:
        return ""
    blocks = re.split(r"\n\s*\n", body.strip())
    pieces: list[str] = []
    for b in blocks:
        b = b.rstrip()
        if not b:
            continue
        if b.startswith("## "):
            pieces.append(f"<h2>{_inline(b[3:].strip())}</h2>")
        elif b.startswith("### "):
            pieces.append(f"<h3>{_inline(b[4:].strip())}</h3>")
        elif b.startswith("> "):
            inner = "\n".join(line[2:] if line.startswith("> ") else line for line in b.splitlines())
            pieces.append(f"<blockquote>{_inline(inner)}</blockquote>")
        elif all(line.lstrip().startswith("- ") for line in b.splitlines() if line.strip()):
            items = [f"<li>{_inline(line.lstrip()[2:])}</li>" for line in b.splitlines() if line.strip()]
            pieces.append("<ul>" + "".join(items) + "</ul>")
        else:
            text = " ".join(line.strip() for line in b.splitlines())
            pieces.append(f"<p>{_inline(text)}</p>")
    return "\n        ".join(pieces)


# ----------------------------------------------------------------------------
# Normalisation
# ----------------------------------------------------------------------------

def _strip_leading_slash(path: str) -> str:
    return path.lstrip("/") if path else path


def normalise_legacy(entry: dict) -> dict:
    scores = entry.get("scores", {}) or {}
    return {
        "source": "legacy",
        "slug": entry["slug"],
        "href": entry.get("href") or f"reviews/{entry['slug']}.html",
        "date_iso": entry.get("date"),
        "restaurant_name": entry.get("restaurant_name", ""),
        "blurb": entry.get("blurb", ""),
        "homepage_blurb": entry.get("homepage_blurb") or entry.get("blurb", ""),
        "homepage_thumb": entry.get("homepage_thumb") or entry.get("thumb", ""),
        "suburb_slug": entry.get("suburb_slug", ""),
        "suburb_display": entry.get("suburb_display", ""),
        "cuisine_slug": entry.get("cuisine_slug", ""),
        "cuisine_display": entry.get("cuisine_display", ""),
        "scores": {
            "comfort": float(scores.get("comfort", 0)),
            "soul": float(scores.get("soul", 0)),
            "mastery": float(scores.get("mastery", 0)),
            "taste": float(scores.get("taste", 0)),
            "die_happy": float(scores.get("die_happy", 0)),
        },
        "archive_grid_html": entry.get("archive_grid_html", ""),
        "archive_list_html": entry.get("archive_list_html", ""),
    }


def normalise_cms(entry: dict, slug: str) -> dict:
    scores = entry.get("scores", {}) or {}
    suburb_display = (entry.get("suburb") or "").strip()
    cuisine_display = (entry.get("cuisine") or "").strip()
    hero_photo = _strip_leading_slash(entry.get("hero_photo", ""))
    gallery = []
    for g in entry.get("gallery") or []:
        gallery.append({
            "photo": _strip_leading_slash(g.get("photo", "")),
            "caption": (g.get("caption") or "").strip(),
        })
    tagline = (entry.get("tagline") or "").strip()
    meta_desc = (entry.get("meta_description") or "").strip() or tagline
    return {
        "source": "cms",
        "slug": slug,
        "href": f"reviews/{slug}.html",
        "date_iso": entry["date_visited"],
        "restaurant_name": (entry.get("restaurant_name") or "").strip(),
        "tagline": tagline,
        "blurb": tagline,
        "homepage_blurb": tagline,
        "homepage_thumb": hero_photo,
        "meta_description": meta_desc,
        "suburb_slug": bucket_suburb(suburb_display),
        "suburb_display": suburb_display,
        "cuisine_slug": bucket_cuisine(cuisine_display),
        "cuisine_display": cuisine_display,
        "instagram_handle": (entry.get("instagram_handle") or "").lstrip("@").strip(),
        "hero_photo": hero_photo,
        "hero_caption": (entry.get("hero_caption") or "").strip(),
        "thumb": hero_photo,
        "scores": {
            "comfort": float(scores.get("comfort", 0)),
            "soul": float(scores.get("soul", 0)),
            "mastery": float(scores.get("mastery", 0)),
            "taste": float(scores.get("taste", 0)),
            "die_happy": float(scores.get("die_happy", 0)),
        },
        "gallery": gallery,
        "body_html": md_to_html(entry.get("body", "")),
        "status": entry.get("status", "published"),
    }


# ----------------------------------------------------------------------------
# CMS review page renderer
# ----------------------------------------------------------------------------

CMS_PAGE_TEMPLATE = """<!doctype html>
{marker}
<html lang="en-GB">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" type="image/svg+xml" href="../assets/favicon.svg">
  <link rel="icon" type="image/png" sizes="32x32" href="../assets/favicon-32.png">
  <link rel="apple-touch-icon" sizes="180x180" href="../assets/apple-touch-icon.png">
  <link rel="shortcut icon" href="../favicon.ico">
  <title>{title}</title>
  <meta name="description" content="{meta_desc}">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Archivo+Black&family=Instrument+Serif:ital@0;1&family=Inter+Tight:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="../assets/styles.css">
</head>
<body>
  <header class="site-header">
    <div class="container">
      <a class="brand-mark" href="../index.html" aria-label="Sasenka Loves Food, home">
        <svg viewBox="0 0 600 220" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
          <text x="0" y="78" font-family="Archivo Black, Arial Black, Impact, sans-serif" font-size="78" font-weight="900" fill="#1D1D1D" letter-spacing="-2">SASENKA</text>
          <text x="0" y="160" font-family="Archivo Black, Arial Black, Impact, sans-serif" font-size="78" font-weight="900" fill="#1D1D1D" letter-spacing="-2">L</text>
          <g transform="translate(44 105) scale(0.47)">
            <path d="M134.756 39.507C134.756 90.727 67.378 117.057 67.378 117.057C67.378 117.057 0 90.727 0 39.507C0 17.681 16.28 0 36.376 0C49.472 0 60.965 7.523 67.378 18.785C73.791 7.523 85.284 0 98.38 0C118.499 0 134.756 17.681 134.756 39.507Z" fill="#BD112E"/>
          </g>
          <text x="108" y="160" font-family="Archivo Black, Arial Black, Impact, sans-serif" font-size="78" font-weight="900" fill="#1D1D1D" letter-spacing="-2">VES</text>
          <text x="0" y="218" font-family="Archivo Black, Arial Black, Impact, sans-serif" font-size="78" font-weight="900" fill="#1D1D1D" letter-spacing="-2">FOOD.</text>
        </svg>
      </a>
      <nav class="site-nav" aria-label="Primary">
        <a href="../index.html">Home</a>
        <a href="../reviews-archive.html">Reviews</a>
        <a href="../rating-system.html">Rating system</a>
        <a href="../about.html">About</a>
        <a href="https://instagram.com/sasenkalovesfood" target="_blank" rel="noopener">Instagram</a>
      </nav>
    </div>
  </header>

  <main>
    <section class="container">
      <div class="review-hero">
        <div class="photo" data-caption="{hero_caption}" style="background-image:url('../{hero_photo}');"></div>
        <div>
          <span class="eyebrow">Review &middot; {month_label}</span>
          <h1>{restaurant_name}</h1>
          <p class="italic">{tagline_html}</p>
        </div>
      </div>

      <div class="fact-bar">
        <div class="fact"><span class="label">Location</span>{suburb}</div>
        <div class="fact"><span class="label">Cuisine</span>{cuisine}</div>
        <div class="fact"><span class="label">Visited</span>{date_long}</div>
        {ig_fact}
      </div>

      <section aria-label="Ratings">
        <div class="scores">
          <div class="score"><span class="label">Comfort</span><span class="value">{comfort}<span class="out">/10</span></span></div>
          <div class="score"><span class="label">Soul</span><span class="value">{soul}<span class="out">/10</span></span></div>
          <div class="score"><span class="label">Mastery</span><span class="value">{mastery}<span class="out">/10</span></span></div>
          <div class="score"><span class="label">Taste</span><span class="value">{taste}<span class="out">/10</span></span></div>
          <div class="score die-happy"><span class="label">Would I die happy?</span><span class="value">{die_happy}<span class="out">/10</span></span></div>
        </div>
      </section>

      <article class="review-body">
        {body_html}
      </article>
{gallery_block}
      <a href="../reviews-archive.html" class="back-link">&larr; All reviews</a>
    </section>
  </main>

  <footer class="site-footer">
    <div class="container">
      <a class="brand-mark" href="../index.html" aria-label="Sasenka Loves Food, home">
        <svg viewBox="0 0 600 220" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
          <text x="0" y="78" font-family="Archivo Black, Arial Black, Impact, sans-serif" font-size="78" font-weight="900" fill="#1D1D1D" letter-spacing="-2">SASENKA</text>
          <text x="0" y="160" font-family="Archivo Black, Arial Black, Impact, sans-serif" font-size="78" font-weight="900" fill="#1D1D1D" letter-spacing="-2">L</text>
          <g transform="translate(44 105) scale(0.47)">
            <path d="M134.756 39.507C134.756 90.727 67.378 117.057 67.378 117.057C67.378 117.057 0 90.727 0 39.507C0 17.681 16.28 0 36.376 0C49.472 0 60.965 7.523 67.378 18.785C73.791 7.523 85.284 0 98.38 0C118.499 0 134.756 17.681 134.756 39.507Z" fill="#BD112E"/>
          </g>
          <text x="108" y="160" font-family="Archivo Black, Arial Black, Impact, sans-serif" font-size="78" font-weight="900" fill="#1D1D1D" letter-spacing="-2">VES</text>
          <text x="0" y="218" font-family="Archivo Black, Arial Black, Impact, sans-serif" font-size="78" font-weight="900" fill="#1D1D1D" letter-spacing="-2">FOOD.</text>
        </svg>
      </a>
      <a class="footer-ig" href="https://instagram.com/sasenkalovesfood" target="_blank" rel="noopener">
        <svg class="ig-glyph" viewBox="0 0 24 24" aria-hidden="true">
          <rect x="3" y="3" width="18" height="18" rx="5" fill="none" stroke="currentColor" stroke-width="1.6"/>
          <circle cx="12" cy="12" r="4" fill="none" stroke="currentColor" stroke-width="1.6"/>
          <circle cx="17.5" cy="6.5" r="1.1" fill="currentColor"/>
        </svg>
        <span>Find me on Instagram, @sasenkalovesfood</span>
      </a>
      <span class="site-footer__copy">&copy; 2026 Sasenka Loves Food</span>
    </div>
  </footer>
  <script src="../assets/lightbox.js" defer></script>
</body>
</html>
"""


def render_cms_review_page(r: dict) -> str:
    ig = r.get("instagram_handle", "")
    ig_fact = ""
    if ig:
        ig_fact = (
            '<div class="fact"><span class="label">Instagram</span>'
            f'<a href="https://instagram.com/{esc(ig)}" target="_blank" rel="noopener">@{esc(ig)}</a></div>'
        )

    tagline = r.get("tagline", "")
    tagline_html = esc(tagline)
    if ig and f"@{ig}" in tagline:
        tagline_html = tagline_html.replace(
            f"@{ig}",
            f'<a href="https://instagram.com/{esc(ig)}" target="_blank" rel="noopener">@{esc(ig)}</a>',
        )

    gallery_block = ""
    if r.get("gallery"):
        figures = []
        for g in r["gallery"]:
            caption = g.get("caption", "")
            figures.append(
                f'          <figure>\n'
                f'            <div class="photo" data-caption="{esc(caption)}" '
                f'style="background-image:url(\'../{g["photo"]}\');"></div>\n'
                f'            <figcaption>{esc(caption)}</figcaption>\n'
                f'          </figure>'
            )
        gallery_block = (
            '\n      <section class="gallery" aria-label="Photos">\n'
            '        <h2>From the meal</h2>\n'
            '        <div class="gallery-grid">\n'
            + "\n".join(figures) + "\n"
            '        </div>\n'
            '      </section>\n'
        )

    return CMS_PAGE_TEMPLATE.format(
        marker=f"<!-- GENERATED FROM data/reviews/{r['slug']}.json. Edit in the CMS. -->",
        title=esc(f"{r['restaurant_name']}, {r['suburb_display']} \u00b7 Sasenka Loves Food"),
        meta_desc=esc(r.get("meta_description", r.get("tagline", ""))),
        hero_caption=esc(r.get("hero_caption", "")),
        hero_photo=r["hero_photo"],
        month_label=month_label(r["date_iso"]),
        restaurant_name=esc(r["restaurant_name"]),
        tagline_html=tagline_html,
        suburb=esc(r["suburb_display"]),
        cuisine=esc(r["cuisine_display"]),
        date_long=ordinal_date(r["date_iso"]),
        ig_fact=ig_fact,
        comfort=fmt_score(r["scores"]["comfort"]),
        soul=fmt_score(r["scores"]["soul"]),
        mastery=fmt_score(r["scores"]["mastery"]),
        taste=fmt_score(r["scores"]["taste"]),
        die_happy=fmt_score(r["scores"]["die_happy"]),
        body_html=r["body_html"],
        gallery_block=gallery_block,
    )


# ----------------------------------------------------------------------------
# Homepage fragments
# ----------------------------------------------------------------------------

def _homepage_thumb(r: dict) -> str:
    return r.get("homepage_thumb") or r.get("thumb") or r.get("hero_photo") or ""


def _homepage_blurb(r: dict) -> str:
    # legacy entries preserve any hand-tuned escaping (e.g. &quot;) in the
    # snapshot, so we don't re-escape here. CMS entries come in as plain
    # text and also flow through as-is; the CMS never produces HTML in the
    # tagline field, so this is safe.
    return r.get("homepage_blurb") or r.get("blurb") or r.get("tagline", "")


def render_featured(r: dict) -> str:
    meta = (
        f"Latest &middot; {esc(r['suburb_display'])} &middot; "
        f"{esc(r['cuisine_display'])} &middot; {month_label(r['date_iso'])}"
    )
    return (
        f'      <a class="feature-review" href="{esc(r["href"])}">\n'
        f'        <div class="photo" style="background-image: url(\'{_homepage_thumb(r)}\');"></div>\n'
        f'        <div class="body">\n'
        f'          <div class="meta">{meta}</div>\n'
        f'          <h2>{esc(r["restaurant_name"])}</h2>\n'
        f'          <p class="blurb">{_homepage_blurb(r)}</p>\n'
        f'          <div class="scores-mini">\n'
        f'            <span class="score-pill">Comfort <strong>{fmt_score(r["scores"]["comfort"])}</strong></span>\n'
        f'            <span class="score-pill">Soul <strong>{fmt_score(r["scores"]["soul"])}</strong></span>\n'
        f'            <span class="score-pill">Mastery <strong>{fmt_score(r["scores"]["mastery"])}</strong></span>\n'
        f'            <span class="score-pill">Taste <strong>{fmt_score(r["scores"]["taste"])}</strong></span>\n'
        f'            <span class="score-pill die-happy">Die happy <strong>{fmt_score(r["scores"]["die_happy"])}</strong></span>\n'
        f'          </div>\n'
        f'        </div>\n'
        f'      </a>'
    )


def render_homepage_card(r: dict) -> str:
    return (
        f'        <a class="review-card" href="{esc(r["href"])}">\n'
        f'          <div class="thumb" style="background-image: url(\'{_homepage_thumb(r)}\');"></div>\n'
        f'          <div class="body">\n'
        f'            <div class="meta">\n'
        f'              <span>{esc(r["suburb_display"])} &middot; {esc(r["cuisine_display"])}</span>\n'
        f'              <span class="dot">&bull;</span>\n'
        f'              <span>{month_year_short(r["date_iso"])}</span>\n'
        f'            </div>\n'
        f'            <h3>{esc(r["restaurant_name"])}</h3>\n'
        f'            <p class="blurb">{_homepage_blurb(r)}</p>\n'
        f'            <div class="scores-mini">\n'
        f'              <span class="score-pill">Comfort <strong>{fmt_score(r["scores"]["comfort"])}</strong></span>\n'
        f'              <span class="score-pill">Soul <strong>{fmt_score(r["scores"]["soul"])}</strong></span>\n'
        f'              <span class="score-pill">Mastery <strong>{fmt_score(r["scores"]["mastery"])}</strong></span>\n'
        f'              <span class="score-pill">Taste <strong>{fmt_score(r["scores"]["taste"])}</strong></span>\n'
        f'              <span class="score-pill die-happy">Die happy <strong>{fmt_score(r["scores"]["die_happy"])}</strong></span>\n'
        f'            </div>\n'
        f'          </div>\n'
        f'        </a>'
    )


def render_homepage_grid(reviews: list[dict]) -> str:
    cards = [render_homepage_card(r) for r in reviews]
    return (
        '      <div class="review-grid">\n\n'
        + "\n\n".join(cards)
        + "\n\n      </div>"
    )


# ----------------------------------------------------------------------------
# Archive: legacy-verbatim with CMS inserts, plus fresh filter chips
# ----------------------------------------------------------------------------

def _cms_archive_grid_card(r: dict) -> str:
    return (
        f'            <a class="review-card archive-card" href="{esc(r["href"])}"\n'
        f'               data-cuisine="{esc(r["cuisine_slug"])}" data-suburb="{esc(r["suburb_slug"])}"\n'
        f'               data-date="{r["date_iso"]}"\n'
        f'               data-comfort="{fmt_score(r["scores"]["comfort"])}" '
        f'data-soul="{fmt_score(r["scores"]["soul"])}"\n'
        f'               data-mastery="{fmt_score(r["scores"]["mastery"])}" '
        f'data-taste="{fmt_score(r["scores"]["taste"])}" '
        f'data-die="{fmt_score(r["scores"]["die_happy"])}">\n'
        f'              <div class="thumb" style="background-image: url(\'{esc(r["thumb"])}\');"></div>\n'
        f'              <div class="body">\n'
        f'                <div class="meta"><span>{esc(r["suburb_display"])} &middot; '
        f'{esc(r["cuisine_display"])}</span><span class="dot">&bull;</span>'
        f'<span>{short_date(r["date_iso"])}</span></div>\n'
        f'                <h3>{esc(r["restaurant_name"])}</h3>\n'
        f'                <p class="blurb">{esc(r.get("tagline", r.get("blurb","")))}</p>\n'
        f'                <div class="scores-mini">\n'
        f'                  <span class="score-pill">Comfort <strong>{fmt_score(r["scores"]["comfort"])}</strong></span>\n'
        f'                  <span class="score-pill">Soul <strong>{fmt_score(r["scores"]["soul"])}</strong></span>\n'
        f'                  <span class="score-pill">Mastery <strong>{fmt_score(r["scores"]["mastery"])}</strong></span>\n'
        f'                  <span class="score-pill">Taste <strong>{fmt_score(r["scores"]["taste"])}</strong></span>\n'
        f'                  <span class="score-pill die-happy">Die happy <strong>{fmt_score(r["scores"]["die_happy"])}</strong></span>\n'
        f'                </div>\n'
        f'              </div>\n'
        f'            </a>'
    )


def _cms_archive_list_row(r: dict) -> str:
    return (
        f'            <a class="archive-row archive-card" href="{esc(r["href"])}"\n'
        f'               data-cuisine="{esc(r["cuisine_slug"])}" data-suburb="{esc(r["suburb_slug"])}"\n'
        f'               data-date="{r["date_iso"]}"\n'
        f'               data-comfort="{fmt_score(r["scores"]["comfort"])}" '
        f'data-soul="{fmt_score(r["scores"]["soul"])}"\n'
        f'               data-mastery="{fmt_score(r["scores"]["mastery"])}" '
        f'data-taste="{fmt_score(r["scores"]["taste"])}" '
        f'data-die="{fmt_score(r["scores"]["die_happy"])}">\n'
        f'              <div>\n'
        f'                <div class="row-title">{esc(r["restaurant_name"])}</div>\n'
        f'                <div class="row-sub">{ordinal_date(r["date_iso"])}</div>\n'
        f'              </div>\n'
        f'              <div class="row-cuisine">{esc(r["cuisine_display"])}</div>\n'
        f'              <div class="row-suburb">{esc(r["suburb_display"])}</div>\n'
        f'              <div class="row-scores">\n'
        f'                <span class="rs">Comfort <strong>{fmt_score(r["scores"]["comfort"])}</strong></span>\n'
        f'                <span class="rs">Soul <strong>{fmt_score(r["scores"]["soul"])}</strong></span>\n'
        f'                <span class="rs">Mastery <strong>{fmt_score(r["scores"]["mastery"])}</strong></span>\n'
        f'                <span class="rs">Taste <strong>{fmt_score(r["scores"]["taste"])}</strong></span>\n'
        f'                <span class="rs die">Die happy <strong>{fmt_score(r["scores"]["die_happy"])}</strong></span>\n'
        f'              </div>\n'
        f'            </a>'
    )


def render_archive(reviews: list[dict]) -> str:
    groups: dict[str, list[dict]] = {}
    for r in reviews:
        groups.setdefault(month_key(r["date_iso"]), []).append(r)
    ordered_months = sorted(groups.keys(), reverse=True)

    sections = []
    for mk in ordered_months:
        entries = sorted(groups[mk], key=lambda r: r["date_iso"], reverse=True)
        grid_cards = []
        list_rows = []
        for r in entries:
            if r["source"] == "legacy" and r.get("archive_grid_html"):
                grid_cards.append("            " + r["archive_grid_html"])
            else:
                grid_cards.append(_cms_archive_grid_card(r))
            if r["source"] == "legacy" and r.get("archive_list_html"):
                list_rows.append("            " + r["archive_list_html"])
            else:
                list_rows.append(_cms_archive_list_row(r))

        label = month_label(entries[0]["date_iso"])
        sections.append(
            f'        <!-- {label} -->\n'
            f'        <section class="month-group" data-month="{mk}">\n'
            f'          <h2 class="month-head">{label}</h2>\n'
            f'\n'
            f'          <!-- Grid view -->\n'
            f'          <div class="review-grid">\n'
            + "\n".join(grid_cards) + "\n"
            f'          </div>\n'
            f'\n'
            f'          <!-- List view -->\n'
            f'          <div class="archive-list">\n'
            + "\n".join(list_rows) + "\n"
            f'          </div>\n'
            f'        </section>'
        )

    return (
        '      <div class="archive-reviews" data-view="grid">\n\n'
        + "\n\n".join(sections)
        + "\n\n      </div>"
    )


def render_filters(
    reviews: list[dict],
    legacy_filter_chips: dict,
) -> str:
    # Preserve the hand-curated chip rows verbatim. Append new cuisine/suburb
    # chips only for values introduced by CMS reviews that aren't already
    # represented.
    existing_cuisines = set(legacy_filter_chips.get("cuisine_filters") or [])
    existing_suburbs = set(legacy_filter_chips.get("suburb_filters") or [])

    new_cuisines: list[tuple[str, str]] = []
    new_suburbs: list[tuple[str, str]] = []
    seen_c: set[str] = set()
    seen_s: set[str] = set()
    for r in reviews:
        if r["source"] != "cms":
            continue
        cs = r["cuisine_slug"]
        if cs and cs not in existing_cuisines and cs != "all" and cs not in seen_c:
            new_cuisines.append((cs, r["cuisine_display"]))
            seen_c.add(cs)
        ss = r["suburb_slug"]
        if ss and ss not in existing_suburbs and ss != "all" and ss not in seen_s:
            new_suburbs.append((ss, r["suburb_display"]))
            seen_s.add(ss)

    cuisine_html = legacy_filter_chips.get("cuisine_html", "")
    suburb_html = legacy_filter_chips.get("suburb_html", "")

    def _append_chips(row_html: str, category: str, additions: list[tuple[str, str]]) -> str:
        if not additions:
            return row_html
        chips = "\n".join(
            f'          <button type="button" class="chip" '
            f'data-category="{category}" data-filter="{esc(slug)}">{esc(display)}</button>'
            for slug, display in additions
        )
        # Insert chips before the closing </div> of the chip-row block.
        return re.sub(
            r"(</div>)\s*$",
            chips + "\n        \\1",
            row_html,
            count=1,
        )

    cuisine_html = _append_chips(cuisine_html, "cuisine", new_cuisines)
    suburb_html = _append_chips(suburb_html, "suburb", new_suburbs)

    return (
        '      <div class="filter-chips" aria-label="Filters">\n'
        f'        {cuisine_html}\n'
        f'        {suburb_html}\n'
        '      </div>'
    )


# ----------------------------------------------------------------------------
# Links page: photo-tile lobby, every review as a square tile
# ----------------------------------------------------------------------------

def _links_thumb(r: dict) -> str:
    # Legacy entries expose homepage_thumb; CMS entries expose thumb/hero_photo.
    # Fall through in that order so either source renders cleanly.
    return r.get("homepage_thumb") or r.get("thumb") or r.get("hero_photo") or ""


def render_links_tile(r: dict) -> str:
    name = esc(r.get("restaurant_name", ""))
    href = esc(r.get("href", ""))
    thumb = esc(_links_thumb(r))
    return (
        f'        <a class="tile" href="{href}" aria-label="Read the review of {name}">\n'
        f'          <img class="tile-photo" src="{thumb}" alt="" loading="lazy">\n'
        f'          <span class="tile-shade" aria-hidden="true"></span>\n'
        f'          <span class="tile-name">{name}</span>\n'
        f'        </a>'
    )


def render_links_grid(reviews: list[dict]) -> str:
    tiles = [render_links_tile(r) for r in reviews]
    return (
        '      <div class="tile-grid">\n'
        + "\n".join(tiles) + "\n"
        '      </div>'
    )


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

def load_all_reviews() -> tuple[list[dict], dict]:
    legacy_doc = json.loads(DATA_LEGACY.read_text(encoding="utf-8"))
    reviews: list[dict] = [normalise_legacy(e) for e in legacy_doc.get("reviews", [])]
    filter_chips = legacy_doc.get("filter_chips", {})

    if DATA_REVIEWS_DIR.exists():
        legacy_slugs = {r["slug"] for r in reviews}
        for p in sorted(DATA_REVIEWS_DIR.glob("*.json")):
            if p.name.startswith("."):
                continue
            raw = json.loads(p.read_text(encoding="utf-8"))
            if raw.get("status") and raw["status"] != "published":
                continue
            slug = p.stem
            entry = normalise_cms(raw, slug)
            reviews = [r for r in reviews if r["slug"] != slug]
            reviews.append(entry)
            if slug in legacy_slugs:
                print(f"  note: CMS review '{slug}' overrides legacy entry")

    reviews.sort(key=lambda r: r.get("date_iso") or "", reverse=True)
    return reviews, filter_chips


def write_cms_review_pages(reviews: Iterable[dict]) -> int:
    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for r in reviews:
        if r.get("source") != "cms":
            continue
        target = REVIEWS_DIR / f"{r['slug']}.html"
        if target.exists():
            head = target.read_text(encoding="utf-8", errors="replace")[:200]
            if GENERATED_MARKER not in head:
                print(f"  skip: {target.name} exists and is hand-edited; CMS entry ignored")
                continue
        target.write_text(render_cms_review_page(r), encoding="utf-8")
        written += 1
    return written


def update_homepage(reviews: list[dict]) -> None:
    if not reviews:
        return
    source = INDEX_HTML.read_text(encoding="utf-8")
    featured = render_featured(reviews[0])
    grid = render_homepage_grid(reviews[1:1 + HOMEPAGE_GRID_SIZE])
    source = replace_marker(source, "FEATURED", featured)
    source = replace_marker(source, "GRID", grid)
    INDEX_HTML.write_text(source, encoding="utf-8")


def update_archive(reviews: list[dict], filter_chips: dict) -> None:
    source = ARCHIVE_HTML.read_text(encoding="utf-8")
    source = replace_marker(source, "FILTERS", render_filters(reviews, filter_chips))
    source = replace_marker(source, "ARCHIVE", render_archive(reviews))
    ARCHIVE_HTML.write_text(source, encoding="utf-8")


def update_links(reviews: list[dict]) -> None:
    # links.html is the Instagram-bio lobby. The BUILD:TILES marker frames the
    # photo-tile grid. Reviews are already sorted most-recent-first by
    # load_all_reviews(), so we can drop them in as-is.
    if not LINKS_HTML.exists():
        return
    source = LINKS_HTML.read_text(encoding="utf-8")
    source = replace_marker(source, "TILES", render_links_grid(reviews))
    LINKS_HTML.write_text(source, encoding="utf-8")


def main() -> None:
    reviews, filter_chips = load_all_reviews()
    legacy_n = sum(1 for r in reviews if r["source"] == "legacy")
    cms_n = sum(1 for r in reviews if r["source"] == "cms")
    print(f"Loaded {len(reviews)} reviews ({legacy_n} legacy, {cms_n} from CMS)")

    written = write_cms_review_pages(reviews)
    if written:
        print(f"Wrote {written} CMS review page(s) to /reviews/")

    update_homepage(reviews)
    print("Updated index.html")

    update_archive(reviews, filter_chips)
    print("Updated reviews-archive.html")

    update_links(reviews)
    print("Updated links.html")


if __name__ == "__main__":
    main()
