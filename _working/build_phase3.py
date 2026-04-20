#!/usr/bin/env python3
"""Phase 3 build for Sasenka Loves Food.

Reads `phase2-final.json` and performs three steps:
 1. Copy photos from `_working/sources/food_reviews/<slug>/photos` into
    `assets/reviews/<slug>/`, converting `.heic` photos to `.jpg` along the way.
    Videos (`.mp4`) are skipped because the review template only uses stills.
 2. Generate one HTML file per included review under `reviews/`, using the
    pattern established by `reviews/_template.html`.
 3. Extend `reviews-archive.html` with new cuisine + suburb filter chips and
    new grid + list cards for every new review, inserted into the correct
    month group (existing May 2025 + April 2025 sections are preserved).

Idempotent: re-running overwrites generated pages + archive additions.
"""
import html
import json
import os
import re
import shutil
from datetime import datetime

from PIL import Image
import pillow_heif

pillow_heif.register_heif_opener()

ROOT = "/sessions/kind-eloquent-meitner/mnt/SLF/sasenka-loves-food"
WORK = os.path.join(ROOT, "_working")
SOURCES = os.path.join(WORK, "sources", "food_reviews")
DATA = os.path.join(WORK, "phase2-final.json")
ASSETS = os.path.join(ROOT, "assets", "reviews")
REVIEWS = os.path.join(ROOT, "reviews")
ARCHIVE = os.path.join(ROOT, "reviews-archive.html")


# -------- Display name helpers -------- #
CUISINE_DISPLAY = {
    "cantonese": "Cantonese",
    "chinese": "Chinese",
    "creole": "Creole",
    "european-brasserie": "European brasserie",
    "french": "French",
    "french-bistro": "French bistro",
    "greek": "Greek",
    "italian": "Italian",
    "italian-degustation": "Italian degustation",
    "japanese": "Japanese",
    "korean": "Korean",
    "malaysian": "Malaysian",
    "mediterranean": "Mediterranean",
    "middle-eastern": "Middle Eastern",
    "modern-asian": "Modern Asian",
    "modern-australian": "Modern Australian",
    "modern-middle-eastern": "Modern Middle Eastern",
    "nepali": "Nepali / Himalayan",
    "nordic": "Nordic",
    "seafood": "Seafood",
    "singaporean": "Singaporean",
    "sri-lankan": "Sri Lankan",
    "steakhouse": "Steakhouse",
    "thai": "Thai",
    "wood-fired": "Wood-fired",
}

SUBURB_DISPLAY = {
    "ballina": "Ballina",
    "brisbane-cbd": "Brisbane CBD",
    "carlton": "Carlton",
    "coorparoo": "Coorparoo",
    "delft": "Delft",
    "fortitude-valley": "Fortitude Valley",
    "greenslopes": "Greenslopes",
    "hobart": "Hobart",
    "james-street": "James Street",
    "maleny": "Maleny",
    "melbourne": "Melbourne",
    "montville": "Montville",
    "morningside": "Morningside",
    "new-farm": "New Farm",
    "newstead": "Newstead",
    "noosa": "Noosa",
    "paddington": "Paddington",
    "rhodes": "Rhodes",
    "singapore": "Singapore",
    "south-brisbane": "South Brisbane",
    "southbank": "South Bank",
    "spring-hill": "Spring Hill",
    "west-end": "West End",
    "woolloongabba": "Woolloongabba",
}


def cuisine_label(key):
    return CUISINE_DISPLAY.get(key, key.replace("-", " ").title() if key else "")


def suburb_label(key):
    return SUBURB_DISPLAY.get(key, key.replace("-", " ").title() if key else "")


def month_label(date_iso):
    dt = datetime.fromisoformat(date_iso.replace("Z", ""))
    return dt.strftime("%B %Y")


def short_date(date_iso):
    dt = datetime.fromisoformat(date_iso.replace("Z", ""))
    # eg "9 April 2026"
    return f"{dt.day} {dt.strftime('%B %Y')}"


def short_date_abbrev(date_iso):
    dt = datetime.fromisoformat(date_iso.replace("Z", ""))
    # eg "9 Apr 2026"
    return f"{dt.day} {dt.strftime('%b %Y')}"


def pascal_name(name):
    """Turn 'Aunty' / "Billy's Pine and Bamboo" into PascalCase without punctuation."""
    parts = re.split(r"[\s\-_/]+", name or "")
    pieces = []
    for p in parts:
        p = re.sub(r"[^A-Za-z0-9]", "", p)
        if not p:
            continue
        pieces.append(p[:1].upper() + p[1:])
    return "".join(pieces) or "Review"


def html_filename(review):
    dt = datetime.fromisoformat(review["date_iso"].replace("Z", ""))
    prefix = dt.strftime("%Y%m%d")
    return f"{prefix}-{pascal_name(review['restaurant_name'])}.html"


# -------- Photo copy step -------- #
def copy_photos(review):
    slug = review["slug"]
    src_dir = os.path.join(SOURCES, slug, "photos")
    dst_dir = os.path.join(ASSETS, slug)
    os.makedirs(dst_dir, exist_ok=True)

    # Build an index of source files by their stem
    if not os.path.isdir(src_dir):
        print(f"  ! missing source dir: {src_dir}")
        return

    # Map from target filename (as listed in phase2) back to actual source file
    # on disk. Phase 2 listed filenames verbatim from the photos folder, but
    # HEIC -> JPG conversion changes the extension, so we also track rename.
    rename_map = {}
    target_filenames = {p["filename"] for p in review["photos"] if not p["is_video"]}
    source_files = os.listdir(src_dir)

    for p in review["photos"]:
        if p["is_video"]:
            continue
        original_name = p["filename"]
        src = os.path.join(src_dir, original_name)
        if not os.path.exists(src):
            # Try alternative case/extension
            stem = os.path.splitext(original_name)[0]
            candidates = [f for f in source_files if f.startswith(stem)]
            if candidates:
                src = os.path.join(src_dir, candidates[0])
                original_name = candidates[0]
            else:
                print(f"  ! missing photo: {src}")
                continue

        is_heic = original_name.lower().endswith(".heic")
        if is_heic:
            new_name = os.path.splitext(original_name)[0] + ".jpg"
            dst = os.path.join(dst_dir, new_name)
            if not os.path.exists(dst):
                try:
                    img = Image.open(src)
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                    img.save(dst, "JPEG", quality=88, optimize=True)
                except Exception as exc:
                    print(f"  ! heic convert failed {src}: {exc}")
                    continue
            rename_map[original_name] = new_name
        else:
            dst = os.path.join(dst_dir, original_name)
            if not os.path.exists(dst):
                shutil.copy2(src, dst)
            rename_map[original_name] = original_name

    return rename_map


# -------- Review page rendering -------- #

PICTURED_RE = re.compile(r"\n\s*(?:pictured|ratings?|rating\s*out|rating\s*\(|star\s*rating|food\s*:\s*[★⭐])", re.IGNORECASE)


def body_paragraphs(caption_source):
    """Extract the prose portion of the Instagram caption, dropping the
    dish list, scores, and hashtags.
    """
    cs = (caption_source or "").strip()
    m = PICTURED_RE.search("\n" + cs)
    if m:
        cs = ("\n" + cs)[: m.start()].strip()
    # Drop trailing hashtags (e.g. "#SasenkaLovesFood ...")
    cs = re.sub(r"\n+#\S[\s\S]*$", "", cs).strip()
    # Split on blank lines
    paras = [p.strip() for p in re.split(r"\n\s*\n+", cs) if p.strip()]
    # Collapse inner single newlines into spaces
    paras = [re.sub(r"\s*\n\s*", " ", p) for p in paras]
    return paras


def linkify_mentions(text):
    def sub(m):
        handle = m.group(1)
        return f'<a href="https://instagram.com/{handle}" target="_blank" rel="noopener">@{handle}</a>'
    return re.sub(r"@([A-Za-z0-9_\.]+)", sub, text)


def html_escape_para(text):
    # Escape HTML first, then linkify @handles (which we then must not
    # re-escape).
    escaped = html.escape(text, quote=False)
    return linkify_mentions(escaped)


TEMPLATE_HEAD = """<!doctype html>
<html lang="en-GB">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title_head}</title>
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
        <div class="photo" data-caption="{hero_cap_attr}" style="background-image:url('{hero_url}');"></div>
        <div>
          <span class="eyebrow">Review &middot; {month_label}</span>
          <h1>{h1}</h1>
          <p class="italic">{standfirst_html}</p>
        </div>
      </div>

      <div class="fact-bar">
        <div class="fact"><span class="label">Location</span>{location_text}</div>
        <div class="fact"><span class="label">Cuisine</span>{cuisine_text}</div>
        <div class="fact"><span class="label">Visited</span>{visit_date}</div>
        {instagram_fact}
      </div>

      <section aria-label="Ratings">
        <div class="scores">
          <div class="score"><span class="label">Comfort</span><span class="value">{sc_comfort}<span class="out">/10</span></span></div>
          <div class="score"><span class="label">Soul</span><span class="value">{sc_soul}<span class="out">/10</span></span></div>
          <div class="score"><span class="label">Mastery</span><span class="value">{sc_mastery}<span class="out">/10</span></span></div>
          <div class="score"><span class="label">Taste</span><span class="value">{sc_taste}<span class="out">/10</span></span></div>
          <div class="score die-happy"><span class="label">Would I die happy?</span><span class="value">{sc_die}<span class="out">/10</span></span></div>
        </div>
      </section>

      <article class="review-body">
{body_paragraphs_html}
      </article>

{gallery_html}

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


def fmt_score(v):
    if v is None:
        return "&mdash;"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "&mdash;"
    return f"{f:.1f}"


def render_review(review, rename_map):
    slug = review["slug"]
    name = review["restaurant_name"] or slug
    cuisine_key = review["cuisine_bucket"]
    suburb_key = review["suburb_bucket"]
    cuisine = cuisine_label(cuisine_key)
    suburb = suburb_label(suburb_key)

    # Hero photo: apply rename map for HEIC conversions
    hero = review.get("hero_photo") or ""
    hero = rename_map.get(hero, hero)
    hero_url = f"../assets/reviews/{slug}/{hero}" if hero else "../assets/placeholder-1.svg"
    hero_cap = review.get("hero_caption") or ""

    standfirst = review.get("standfirst") or ""

    # Instagram fact
    handle = review.get("instagram_handle") or ""
    if handle:
        instagram_fact = (
            f'<div class="fact"><span class="label">Instagram</span>'
            f'<a href="https://instagram.com/{html.escape(handle)}" target="_blank" rel="noopener">'
            f"@{html.escape(handle)}</a></div>"
        )
    else:
        instagram_fact = ""

    scores = review.get("scores") or {}

    # Body paragraphs
    paras = body_paragraphs(review.get("caption_source") or "")
    body_html_parts = []
    for p in paras:
        body_html_parts.append(f"        <p>{html_escape_para(p)}</p>")
    if not body_html_parts:
        body_html_parts.append("        <p>Full write-up coming soon.</p>")
    body_paragraphs_html = "\n".join(body_html_parts)

    # Gallery
    gallery_figs = []
    for p in review.get("photos") or []:
        if p.get("is_video"):
            continue
        fn = p["filename"]
        fn = rename_map.get(fn, fn)
        cap = p.get("caption") or ""
        cap_attr = html.escape(cap, quote=True)
        fig = (
            "          <figure>\n"
            f"            <div class=\"photo\" data-caption=\"{cap_attr}\" style=\"background-image:url('../assets/reviews/{slug}/{fn}');\"></div>\n"
            f"            <figcaption>{html.escape(cap)}</figcaption>\n"
            "          </figure>"
        )
        gallery_figs.append(fig)
    if gallery_figs:
        gallery_html = (
            '      <section class="gallery" aria-label="Photos">\n'
            "        <h2>From the meal</h2>\n"
            '        <div class="gallery-grid">\n'
            + "\n".join(gallery_figs)
            + "\n        </div>\n"
            "      </section>"
        )
    else:
        gallery_html = ""

    title_city = suburb if suburb else ""
    title_core = html.escape(f"{name}{', ' + title_city if title_city else ''}")
    title_head = f"{title_core} &middot; Sasenka Loves Food"
    meta_desc = html.escape(standfirst or f"A review of {name}.", quote=True)

    rendered = TEMPLATE_HEAD.format(
        title_head=title_head,
        meta_desc=meta_desc,
        hero_cap_attr=html.escape(hero_cap, quote=True),
        hero_url=hero_url,
        month_label=month_label(review["date_iso"]),
        h1=html.escape(name),
        standfirst_html=html_escape_para(standfirst) if standfirst else "",
        location_text=html.escape(suburb) if suburb else "",
        cuisine_text=html.escape(cuisine) if cuisine else "",
        visit_date=short_date(review["date_iso"]),
        instagram_fact=instagram_fact,
        sc_comfort=fmt_score(scores.get("comfort")),
        sc_soul=fmt_score(scores.get("soul")),
        sc_mastery=fmt_score(scores.get("mastery")),
        sc_taste=fmt_score(scores.get("taste")),
        sc_die=fmt_score(scores.get("would_i_die_happy")),
        body_paragraphs_html=body_paragraphs_html,
        gallery_html=gallery_html,
    )
    return rendered


# -------- Archive extension -------- #

def blurb_from_standfirst(s):
    s = (s or "").strip()
    if not s:
        return ""
    # trim to a single sentence, keep it short
    if len(s) > 240:
        s = s[:237].rsplit(" ", 1)[0] + "..."
    return s


def render_grid_card(review, rename_map):
    slug = review["slug"]
    name = review["restaurant_name"] or slug
    cuisine_key = review["cuisine_bucket"]
    suburb_key = review["suburb_bucket"]
    cuisine = cuisine_label(cuisine_key)
    suburb = suburb_label(suburb_key)
    hero = review.get("hero_photo") or ""
    hero = rename_map.get(hero, hero)
    thumb_url = f"assets/reviews/{slug}/{hero}" if hero else "assets/placeholder-1.svg"
    scores = review.get("scores") or {}
    href = f"reviews/{html_filename(review)}"
    blurb = blurb_from_standfirst(review.get("standfirst"))
    return (
        f'            <a class="review-card archive-card" href="{href}"\n'
        f'               data-cuisine="{cuisine_key}" data-suburb="{suburb_key}"\n'
        f'               data-date="{review["date_iso"][:10]}"\n'
        f'               data-comfort="{fmt_score(scores.get("comfort"))}" data-soul="{fmt_score(scores.get("soul"))}" data-mastery="{fmt_score(scores.get("mastery"))}" data-taste="{fmt_score(scores.get("taste"))}" data-die="{fmt_score(scores.get("would_i_die_happy"))}">\n'
        f'              <div class="thumb" style="background-image: url(\'{thumb_url}\');"></div>\n'
        f'              <div class="body">\n'
        f'                <div class="meta"><span>{html.escape(suburb)} &middot; {html.escape(cuisine)}</span><span class="dot">&bull;</span><span>{short_date_abbrev(review["date_iso"])}</span></div>\n'
        f'                <h3>{html.escape(name)}</h3>\n'
        f'                <p class="blurb">{html.escape(blurb)}</p>\n'
        f'                <div class="scores-mini">\n'
        f'                  <span class="score-pill">Comfort <strong>{fmt_score(scores.get("comfort"))}</strong></span>\n'
        f'                  <span class="score-pill">Soul <strong>{fmt_score(scores.get("soul"))}</strong></span>\n'
        f'                  <span class="score-pill">Mastery <strong>{fmt_score(scores.get("mastery"))}</strong></span>\n'
        f'                  <span class="score-pill">Taste <strong>{fmt_score(scores.get("taste"))}</strong></span>\n'
        f'                  <span class="score-pill die-happy">Die happy <strong>{fmt_score(scores.get("would_i_die_happy"))}</strong></span>\n'
        f'                </div>\n'
        f'              </div>\n'
        f'            </a>\n'
    )


def render_list_row(review):
    slug = review["slug"]
    name = review["restaurant_name"] or slug
    cuisine_key = review["cuisine_bucket"]
    suburb_key = review["suburb_bucket"]
    cuisine = cuisine_label(cuisine_key)
    suburb = suburb_label(suburb_key)
    scores = review.get("scores") or {}
    href = f"reviews/{html_filename(review)}"
    return (
        f'            <a class="archive-row archive-card" href="{href}"\n'
        f'               data-cuisine="{cuisine_key}" data-suburb="{suburb_key}"\n'
        f'               data-date="{review["date_iso"][:10]}"\n'
        f'               data-comfort="{fmt_score(scores.get("comfort"))}" data-soul="{fmt_score(scores.get("soul"))}" data-mastery="{fmt_score(scores.get("mastery"))}" data-taste="{fmt_score(scores.get("taste"))}" data-die="{fmt_score(scores.get("would_i_die_happy"))}">\n'
        f'              <div>\n'
        f'                <div class="row-title">{html.escape(name)}</div>\n'
        f'                <div class="row-sub">{short_date(review["date_iso"])}</div>\n'
        f'              </div>\n'
        f'              <div class="row-cuisine">{html.escape(cuisine)}</div>\n'
        f'              <div class="row-suburb">{html.escape(suburb)}</div>\n'
        f'              <div class="row-scores">\n'
        f'                <span class="rs">Comfort <strong>{fmt_score(scores.get("comfort"))}</strong></span>\n'
        f'                <span class="rs">Soul <strong>{fmt_score(scores.get("soul"))}</strong></span>\n'
        f'                <span class="rs">Mastery <strong>{fmt_score(scores.get("mastery"))}</strong></span>\n'
        f'                <span class="rs">Taste <strong>{fmt_score(scores.get("taste"))}</strong></span>\n'
        f'                <span class="rs die">Die happy <strong>{fmt_score(scores.get("would_i_die_happy"))}</strong></span>\n'
        f'              </div>\n'
        f'            </a>\n'
    )


def render_month_group(month_key, reviews, rename_maps):
    """Render a complete month-group section (grid + list) for new months."""
    dt = datetime.strptime(month_key + "-01", "%Y-%m-%d")
    label = dt.strftime("%B %Y")
    cards = "".join(render_grid_card(r, rename_maps[r["slug"]]) for r in reviews)
    rows = "".join(render_list_row(r) for r in reviews)
    return (
        f'        <!-- {label} -->\n'
        f'        <section class="month-group" data-month="{month_key}">\n'
        f'          <h2 class="month-head">{label}</h2>\n\n'
        f'          <!-- Grid view -->\n'
        f'          <div class="review-grid">\n{cards}          </div>\n\n'
        f'          <!-- List view -->\n'
        f'          <div class="archive-list">\n{rows}          </div>\n'
        f'        </section>\n\n'
    )


def extend_archive(reviews_by_month, rename_maps):
    with open(ARCHIVE, "r", encoding="utf-8") as fh:
        src = fh.read()

    # 1. Add new cuisine chips. Find cuisine chip-row block, append before </div>
    # We detect which buckets already have chips.
    existing_cuisines = set(re.findall(r'data-category="cuisine" data-filter="([^"]+)"', src))
    existing_suburbs = set(re.findall(r'data-category="suburb" data-filter="([^"]+)"', src))

    new_cuisines = []
    for r_list in reviews_by_month.values():
        for r in r_list:
            c = r["cuisine_bucket"]
            if c and c not in existing_cuisines and c not in new_cuisines:
                new_cuisines.append(c)
    new_suburbs = []
    for r_list in reviews_by_month.values():
        for r in r_list:
            s = r["suburb_bucket"]
            if s and s not in existing_suburbs and s not in new_suburbs:
                new_suburbs.append(s)

    # Sort alphabetically by display label for a predictable chip order
    new_cuisines.sort(key=lambda k: cuisine_label(k).lower())
    new_suburbs.sort(key=lambda k: suburb_label(k).lower())

    cuisine_chip_html = "".join(
        f'          <button type="button" class="chip" data-category="cuisine" data-filter="{c}">{html.escape(cuisine_label(c))}</button>\n'
        for c in new_cuisines
    )
    suburb_chip_html = "".join(
        f'          <button type="button" class="chip" data-category="suburb" data-filter="{s}">{html.escape(suburb_label(s))}</button>\n'
        for s in new_suburbs
    )

    # Inject before the closing </div> of each chip-row block
    def inject_chips(src_text, role, new_chip_html):
        pattern = re.compile(
            r'(<div class="chip-row" role="group" aria-label="' + re.escape(role) + r'">)(.*?)(</div>)',
            re.DOTALL,
        )
        def repl(m):
            inner = m.group(2)
            # Make sure inner ends with a newline + correct indentation
            if not inner.endswith("\n        "):
                inner = inner.rstrip() + "\n"
            return m.group(1) + inner + new_chip_html + "        " + m.group(3)
        return pattern.sub(repl, src_text, count=1)

    if new_cuisines:
        src = inject_chips(src, "Cuisine", cuisine_chip_html)
    if new_suburbs:
        src = inject_chips(src, "Suburb", suburb_chip_html)

    # 2. Insert new month-group sections + augment May 2025.
    # The archive-reviews container currently holds May 2025 then April 2025.
    # Everything newer than May 2025 is a brand-new group.
    may_2025_reviews = reviews_by_month.pop("2025-05", [])
    other_months = sorted(reviews_by_month.keys(), reverse=True)

    # Build new month blocks (everything 2025-06 and later)
    new_month_blocks = ""
    for m in other_months:
        new_month_blocks += render_month_group(m, reviews_by_month[m], rename_maps)

    # Insert new month blocks at the very start of <div class="archive-reviews" ...>
    archive_open = re.search(r'(<div class="archive-reviews"[^>]*>)\s*\n', src)
    if archive_open and new_month_blocks:
        insert_at = archive_open.end()
        src = src[:insert_at] + "\n" + new_month_blocks + src[insert_at:]

    # Prepend May 2025 reviews to the existing May 2025 section.
    if may_2025_reviews:
        # Find May 2025 section: <section class="month-group" data-month="2025-05"> ... </section>
        may_pattern = re.compile(
            r'(<section class="month-group" data-month="2025-05">\s*\n\s*<h2 class="month-head">May 2025</h2>\s*\n\s*\n?\s*<!-- Grid view -->\s*\n\s*<div class="review-grid">\s*\n)',
            re.MULTILINE,
        )
        may_grid_cards = "".join(render_grid_card(r, rename_maps[r["slug"]]) for r in may_2025_reviews)
        m = may_pattern.search(src)
        if m:
            src = src[: m.end()] + may_grid_cards + src[m.end():]
        else:
            print("  ! May 2025 grid marker not found, May reviews not injected")

        # Now prepend into the archive-list of the same section
        may_list_pattern = re.compile(
            r'(<section class="month-group" data-month="2025-05">[\s\S]*?<div class="archive-list">\s*\n)',
            re.MULTILINE,
        )
        may_list_rows = "".join(render_list_row(r) for r in may_2025_reviews)
        m = may_list_pattern.search(src)
        if m:
            src = src[: m.end()] + may_list_rows + src[m.end():]
        else:
            print("  ! May 2025 list marker not found, May list rows not injected")

    with open(ARCHIVE, "w", encoding="utf-8") as fh:
        fh.write(src)

    print(f"  new cuisine chips: {len(new_cuisines)} ({new_cuisines})")
    print(f"  new suburb chips: {len(new_suburbs)} ({new_suburbs})")
    print(f"  new month-groups: {len(other_months)} ({other_months})")
    print(f"  may-2025 reviews prepended: {len(may_2025_reviews)}")


# -------- Orchestration -------- #
def main():
    with open(DATA, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    reviews = data["reviews"]
    print(f"Phase 3: {len(reviews)} reviews to process")

    os.makedirs(ASSETS, exist_ok=True)
    os.makedirs(REVIEWS, exist_ok=True)

    rename_maps = {}
    for i, r in enumerate(reviews, 1):
        print(f"[{i}/{len(reviews)}] {r['slug']}")
        rename_maps[r["slug"]] = copy_photos(r) or {}

    print()
    print("Rendering review pages...")
    for r in reviews:
        out_name = html_filename(r)
        out_path = os.path.join(REVIEWS, out_name)
        html_text = render_review(r, rename_maps[r["slug"]])
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(html_text)
    print(f"  wrote {len(reviews)} files to {REVIEWS}")

    print()
    print("Extending archive page...")
    reviews_by_month = {}
    for r in reviews:
        m = r["date_iso"][:7]
        reviews_by_month.setdefault(m, []).append(r)
    for m in reviews_by_month:
        reviews_by_month[m].sort(key=lambda x: x["date_iso"], reverse=True)

    extend_archive(reviews_by_month, rename_maps)

    print()
    print("Done.")


if __name__ == "__main__":
    main()
