#!/usr/bin/env python3
"""Build a single staging HTML page for all 63 parsed reviews.

Reads `_working/phase1-dataset.json` and renders `_working/staging.html`.
Photos are referenced relatively via `sources/food_reviews/<slug>/photos/<file>`.
"""
import html
import json
import os
from datetime import datetime

WORK = "/sessions/kind-eloquent-meitner/mnt/SLF/sasenka-loves-food/_working"
DATASET = os.path.join(WORK, "phase1-dataset.json")
OUT = os.path.join(WORK, "staging.html")

FLAG_LABELS = {
    "missing-restaurant-name": "name?",
    "suburb-unresolved": "suburb?",
    "cuisine-unresolved": "cuisine?",
    "ratings-missing": "scores?",
    "no-pictured-list": "no pictured list",
    "contains-video": "has video",
    "heic-photos": "HEIC (needs convert)",
}


def esc(s):
    if s is None:
        return ""
    return html.escape(str(s), quote=True)


def nl2br(s):
    return esc(s).replace("\n", "<br>")


def render_ratings(r, source):
    if not r:
        src_badge = f'<span class="badge badge-warn">{esc(source)}</span>'
        return f'<div class="ratings ratings-empty">{src_badge}<span class="muted">no numeric ratings in source</span></div>'
    src_class = {
        "json-native": "badge-ok",
        "caption-parsed": "badge-ok",
        "stars-only": "badge-warn",
        "missing": "badge-warn",
    }.get(source, "badge-warn")
    pills = []
    for key, label in [
        ("comfort", "Comfort"),
        ("soul", "Soul"),
        ("mastery", "Mastery"),
        ("taste", "Taste"),
        ("would_i_die_happy", "Die happy"),
    ]:
        v = r.get(key)
        pills.append(
            f'<span class="pill"><span class="pill-label">{label}</span>'
            f'<span class="pill-value">{v if v is not None else "—"}</span></span>'
        )
    src_badge = f'<span class="badge {src_class}">{esc(source)}</span>'
    return f'<div class="ratings">{src_badge}{"".join(pills)}</div>'


def render_stars(stars):
    if not stars:
        return ""
    parts = []
    for k, v in stars.items():
        parts.append(
            f'<span class="pill pill-star"><span class="pill-label">{esc(k.title())}</span>'
            f'<span class="pill-value">{"★" * v}</span></span>'
        )
    return f'<div class="ratings-stars">{"".join(parts)}</div>'


def render_flags(flags):
    if not flags:
        return ""
    chips = []
    for f in flags:
        label = FLAG_LABELS.get(f, f)
        chips.append(f'<span class="flag" data-flag="{esc(f)}">{esc(label)}</span>')
    return f'<div class="flags">{"".join(chips)}</div>'


def render_photos(r):
    photos = r.get("photos") or []
    if not photos:
        return ""
    slug = r["slug"]
    cards = []
    for p in photos:
        fn = p["filename"]
        src = f'sources/food_reviews/{slug}/photos/{fn}'
        is_video = p.get("is_video")
        is_heic = fn.lower().endswith(".heic")
        cap = p.get("caption") or ""
        if is_video:
            media = f'<div class="photo-placeholder">video<br><code>{esc(fn)}</code></div>'
        elif is_heic:
            media = f'<div class="photo-placeholder">HEIC<br><code>{esc(fn)}</code><br><span class="muted">browser can\'t render</span></div>'
        else:
            media = f'<img loading="lazy" src="{esc(src)}" alt="">'
        cards.append(
            f'<figure class="photo-card">{media}'
            f'<figcaption><span class="photo-order">{esc(p.get("order"))}</span>'
            f'{esc(cap) if cap else "<em class=muted>no caption</em>"}</figcaption></figure>'
        )
    return f'<div class="photo-grid">{"".join(cards)}</div>'


def render_hashtags(tags):
    if not tags:
        return ""
    chips = [f'<span class="hash">#{esc(t)}</span>' for t in tags[:12]]
    extra = f' <span class="muted">+{len(tags) - 12} more</span>' if len(tags) > 12 else ""
    return f'<div class="hashtags">{"".join(chips)}{extra}</div>'


def card(r):
    slug = r["slug"]
    date = (r.get("date_iso") or "")[:10]
    name = r.get("restaurant_name") or "(no name)"
    handle = r.get("instagram_handle") or ""
    flag_attrs = " ".join(f'flag-{f}' for f in (r.get("flags") or []))
    attn = "attn" if r.get("flags") else ""

    hero_photo = None
    hero_is_heic = False
    for p in r.get("photos") or []:
        if not p.get("is_video"):
            hero_photo = p["filename"]
            hero_is_heic = hero_photo.lower().endswith(".heic")
            break
    hero_src = f'sources/food_reviews/{slug}/photos/{hero_photo}' if hero_photo and not hero_is_heic else ""

    handle_link = (
        f'<a href="https://instagram.com/{esc(handle)}" target="_blank" rel="noopener">@{esc(handle)}</a>'
        if handle else '<span class="muted">no handle</span>'
    )

    cuisine = r["cuisine"]["bucket"] or "_unresolved_"
    cuisine_existing = r["cuisine"]["is_existing"]
    cuisine_class = "tag-ok" if cuisine_existing else ("tag-new" if r["cuisine"]["bucket"] else "tag-missing")

    suburb = r["suburb"]["bucket"] or "_unresolved_"
    suburb_existing = r["suburb"]["is_existing"]
    suburb_class = "tag-ok" if suburb_existing else ("tag-new" if r["suburb"]["bucket"] else "tag-missing")

    hero_caption = r.get("proposed_hero_caption") or ""
    standfirst = r.get("standfirst_seed_from_source") or ""
    caption_clean = r.get("caption_clean") or ""

    if hero_src:
        hero_block = f'<div class="hero-photo"><img loading="lazy" src="{esc(hero_src)}" alt=""></div>'
    elif hero_is_heic:
        hero_block = f'<div class="hero-photo hero-empty">hero is HEIC<br><code>{esc(hero_photo)}</code><br>needs conversion</div>'
    else:
        hero_block = '<div class="hero-photo hero-empty">no hero photo</div>'

    return f'''
<article class="review-card {attn} {flag_attrs}" id="{esc(slug)}" data-cuisine="{esc(cuisine)}" data-suburb="{esc(suburb)}" data-ratings="{esc(r["ratings_source"])}">
  <header class="card-head">
    <div class="card-head__left">
      {hero_block}
    </div>
    <div class="card-head__right">
      <div class="card-title-row">
        <div>
          <span class="eyebrow">{esc(date)} &middot; #{esc(r.get("order"))}</span>
          <h2>{esc(name)}</h2>
          <p class="handle">{handle_link}</p>
        </div>
        {render_flags(r.get("flags") or [])}
      </div>
      <dl class="meta-grid">
        <dt>Slug</dt><dd><code>{esc(slug)}</code></dd>
        <dt>Cuisine</dt><dd><span class="tag {cuisine_class}">{esc(cuisine)}</span>{" <span class=muted>existing</span>" if cuisine_existing else (" <span class=muted>new bucket proposed</span>" if r["cuisine"]["bucket"] else "")}</dd>
        <dt>Suburb</dt><dd><span class="tag {suburb_class}">{esc(suburb)}</span>{" <span class=muted>existing</span>" if suburb_existing else (" <span class=muted>new bucket proposed</span>" if r["suburb"]["bucket"] else "")}</dd>
        <dt>Photos</dt><dd>{esc(r.get("photo_count", 0))}{(" + " + str(r.get("video_count")) + " video") if r.get("video_count") else ""}</dd>
      </dl>
      {render_ratings(r.get("ratings"), r["ratings_source"])}
      {render_stars(r.get("star_ratings"))}
      <div class="standfirst">
        <span class="label">Proposed hero caption</span>
        <p>{esc(hero_caption) if hero_caption else '<em class="muted">(no pictured list in source)</em>'}</p>
        <span class="label">Standfirst seed from source</span>
        <p class="italic">{esc(standfirst) if standfirst else '<em class="muted">(none picked)</em>'}</p>
      </div>
      <details class="caption-full">
        <summary>Show full cleaned caption</summary>
        <p>{nl2br(caption_clean)}</p>
      </details>
      {render_hashtags(r.get("hashtags"))}
    </div>
  </header>
  <details class="photos-toggle" open>
    <summary>Photos + pictured-list captions ({esc(len(r.get("photos") or []))})</summary>
    {render_photos(r)}
  </details>
</article>
'''


def main():
    with open(DATASET, "r", encoding="utf-8") as fh:
        d = json.load(fh)

    reviews = d["reviews"]
    generated = d.get("generated_at", "")

    # Counters
    total = len(reviews)
    flagged = sum(1 for r in reviews if r.get("flags"))
    unresolved_cuisine = sum(1 for r in reviews if not r["cuisine"]["bucket"])
    unresolved_suburb = sum(1 for r in reviews if not r["suburb"]["bucket"])
    missing_name = sum(1 for r in reviews if not (r.get("restaurant_name") and r.get("instagram_handle")))
    missing_ratings = sum(1 for r in reviews if r["ratings_source"] == "missing")
    stars_only = sum(1 for r in reviews if r["ratings_source"] == "stars-only")
    has_video = sum(1 for r in reviews if any(p.get("is_video") for p in (r.get("photos") or [])))
    has_heic = sum(1 for r in reviews if "heic-photos" in (r.get("flags") or []))

    new_cuisines = d.get("proposed_new_cuisine_buckets", [])
    new_suburbs = d.get("proposed_new_suburb_buckets", [])

    cards = "\n".join(card(r) for r in reviews)

    css = """
:root{
  --ink:#1D1D1D; --ink-muted:#5b5a55; --ink-soft:#8a8882;
  --cream:#F6F1E7; --warm-cream:#ECE5D2; --paper:#FFFDF7;
  --olive:#4B5D3B; --tomato:#BD112E;
  --rule:#d7cfb8; --rule-soft:#e8e2cf;
  --ok:#3f6b3f; --warn:#a06310; --miss:#8b2c1f;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{font:15px/1.55 'Inter Tight', ui-sans-serif, system-ui, sans-serif; background:var(--cream); color:var(--ink)}
a{color:var(--olive)}
.container{max-width:1180px;margin:0 auto;padding:24px}
header.page-head{background:var(--paper);border-bottom:1px solid var(--rule);padding:28px 0 18px}
h1{font-family:'Archivo Black', Arial Black, Impact, sans-serif; letter-spacing:-1px; margin:0 0 4px; font-size:34px}
h2{font-family:'Instrument Serif', 'Times New Roman', serif; font-weight:400; margin:0 0 4px; font-size:28px; line-height:1.05}
.eyebrow{text-transform:uppercase;letter-spacing:.1em;font-size:11px;color:var(--ink-soft);font-weight:600}
.italic{font-family:'Instrument Serif', serif; font-style:italic; color:var(--ink-muted)}
.muted{color:var(--ink-soft)}
code{font-family:'JetBrains Mono', ui-monospace, Menlo, monospace; font-size:12px; background:var(--warm-cream); padding:1px 5px; border-radius:3px}
.stats{display:flex; gap:18px; flex-wrap:wrap; margin-top:12px; font-size:13px; color:var(--ink-muted)}
.stats b{color:var(--ink)}
.legend{margin-top:12px; font-size:12px; color:var(--ink-soft)}
.legend .tag{margin-right:4px}
.filter-bar{position:sticky; top:0; z-index:5; background:var(--cream); padding:14px 0 10px; border-bottom:1px solid var(--rule-soft); display:flex; gap:10px; flex-wrap:wrap; align-items:center}
.filter-bar button{font:inherit; background:var(--paper); border:1px solid var(--rule); color:var(--ink); padding:6px 12px; border-radius:999px; cursor:pointer}
.filter-bar button.is-active{background:var(--ink); color:var(--paper); border-color:var(--ink)}
.filter-bar .filter-group-label{font-size:12px; color:var(--ink-soft); text-transform:uppercase; letter-spacing:.08em; margin-right:4px}
.filter-bar select{font:inherit; background:var(--paper); border:1px solid var(--rule); padding:6px 10px; border-radius:6px}

.review-card{background:var(--paper); border:1px solid var(--rule); border-radius:10px; padding:18px; margin:16px 0; box-shadow:0 1px 0 rgba(0,0,0,.02)}
.review-card.attn{border-left:4px solid var(--tomato)}
.card-head{display:grid; grid-template-columns: 260px 1fr; gap:20px}
.hero-photo{aspect-ratio:4/3; background:var(--warm-cream); border-radius:8px; overflow:hidden; position:relative}
.hero-photo img{width:100%; height:100%; object-fit:cover; display:block}
.hero-photo.hero-empty{display:flex; align-items:center; justify-content:center; color:var(--ink-soft); font-size:12px}
.card-title-row{display:flex; justify-content:space-between; gap:14px; align-items:flex-start; margin-bottom:10px}
.handle{margin:4px 0 0; font-size:13px}

.meta-grid{display:grid; grid-template-columns:90px 1fr; gap:4px 14px; margin:10px 0 12px; font-size:13px}
.meta-grid dt{color:var(--ink-soft); text-transform:uppercase; letter-spacing:.06em; font-size:11px; align-self:center}
.meta-grid dd{margin:0}

.tag{display:inline-block; font-size:12px; padding:2px 8px; border-radius:999px; font-weight:600}
.tag-ok{background:#e6efdf; color:#355429}
.tag-new{background:#fde9d3; color:#7a4a12}
.tag-missing{background:#f5d6d0; color:#7a1f15}

.flags{display:flex; gap:4px; flex-wrap:wrap; margin-left:auto}
.flag{font-size:11px; padding:2px 8px; border-radius:999px; background:#f5d6d0; color:#7a1f15; font-weight:600; text-transform:lowercase}

.ratings{display:flex; gap:6px; flex-wrap:wrap; align-items:center; margin:8px 0 6px}
.ratings-empty{color:var(--ink-soft); font-style:italic}
.ratings-stars{display:flex; gap:6px; flex-wrap:wrap; margin-bottom:8px}
.pill{display:inline-flex; align-items:baseline; gap:4px; background:var(--warm-cream); padding:3px 8px; border-radius:6px; font-size:12px}
.pill-star{background:#f3e8c8}
.pill-label{color:var(--ink-soft); font-weight:600; text-transform:uppercase; letter-spacing:.06em; font-size:10px}
.pill-value{font-family:'Instrument Serif', serif; font-size:15px}
.badge{font-size:10px; padding:2px 7px; border-radius:999px; text-transform:uppercase; letter-spacing:.06em; font-weight:700}
.badge-ok{background:#dce8d4; color:#355429}
.badge-warn{background:#f5ddc3; color:#7a4a12}

.standfirst{border-top:1px dashed var(--rule-soft); margin-top:10px; padding-top:10px}
.standfirst .label{display:block; text-transform:uppercase; letter-spacing:.08em; font-size:10px; color:var(--ink-soft); font-weight:700; margin-top:4px}
.standfirst p{margin:2px 0 6px}

.caption-full{margin-top:8px}
.caption-full summary{cursor:pointer; color:var(--olive); font-size:12px}
.caption-full p{margin:6px 0 0; color:var(--ink-muted); white-space:normal}
.hashtags{margin-top:8px; display:flex; flex-wrap:wrap; gap:4px}
.hash{font-size:11px; color:var(--ink-soft); background:var(--warm-cream); padding:1px 6px; border-radius:4px}

.photos-toggle{margin-top:16px; border-top:1px solid var(--rule-soft); padding-top:12px}
.photos-toggle summary{cursor:pointer; color:var(--olive); font-weight:600; font-size:13px}
.photo-grid{display:grid; grid-template-columns:repeat(auto-fill, minmax(180px, 1fr)); gap:10px; margin-top:10px}
.photo-card{margin:0; background:var(--warm-cream); border-radius:6px; overflow:hidden}
.photo-card img{width:100%; aspect-ratio:1/1; object-fit:cover; display:block}
.photo-placeholder{aspect-ratio:1/1; display:flex; flex-direction:column; align-items:center; justify-content:center; font-size:11px; color:var(--ink-soft); padding:8px; text-align:center; background:#efe6cf; gap:4px; font-weight:600; text-transform:uppercase; letter-spacing:.08em}
.photo-card figcaption{font-size:11px; color:var(--ink-muted); padding:6px 8px; display:flex; gap:6px; min-height:42px}
.photo-order{font-weight:700; color:var(--ink); background:var(--paper); padding:0 6px; border-radius:4px; height:18px; flex-shrink:0}

@media (max-width: 720px){
  .card-head{grid-template-columns: 1fr}
  .meta-grid{grid-template-columns: 70px 1fr}
}
"""

    js = """
const filters = { attention: 'all', cuisine: 'all', suburb: 'all', ratings: 'all' };

function apply() {
  const cards = document.querySelectorAll('.review-card');
  cards.forEach(c => {
    let show = true;
    if (filters.attention === 'flagged' && !c.classList.contains('attn')) show = false;
    if (filters.attention === 'clean' && c.classList.contains('attn')) show = false;
    if (filters.cuisine !== 'all' && c.dataset.cuisine !== filters.cuisine) show = false;
    if (filters.suburb !== 'all' && c.dataset.suburb !== filters.suburb) show = false;
    if (filters.ratings !== 'all' && c.dataset.ratings !== filters.ratings) show = false;
    c.style.display = show ? '' : 'none';
  });
  document.getElementById('visible-count').textContent =
    Array.from(cards).filter(c => c.style.display !== 'none').length;
}

document.addEventListener('click', e => {
  const b = e.target.closest('[data-filter]');
  if (!b) return;
  const group = b.dataset.filter;
  filters[group] = b.dataset.value;
  document.querySelectorAll(`[data-filter="${group}"]`).forEach(x => x.classList.toggle('is-active', x.dataset.value === filters[group]));
  apply();
});
document.addEventListener('change', e => {
  if (e.target.matches('select[data-filter]')) {
    filters[e.target.dataset.filter] = e.target.value;
    apply();
  }
});
"""

    # Build filter options
    cuisines = sorted({r["cuisine"]["bucket"] for r in reviews if r["cuisine"]["bucket"]})
    suburbs = sorted({r["suburb"]["bucket"] for r in reviews if r["suburb"]["bucket"]})
    cuisine_options = "".join(f'<option value="{esc(c)}">{esc(c)}</option>' for c in cuisines)
    suburb_options = "".join(f'<option value="{esc(s)}">{esc(s)}</option>' for s in suburbs)

    legend_new_cuisines = " ".join(f'<span class="tag tag-new">{esc(c)}</span>' for c in new_cuisines) or "—"
    legend_new_suburbs = " ".join(f'<span class="tag tag-new">{esc(s)}</span>' for s in new_suburbs) or "—"

    doc = f"""<!doctype html>
<html lang="en-GB">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Phase 2 staging, {total} reviews — Sasenka Loves Food</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Archivo+Black&family=Instrument+Serif:ital@0;1&family=Inter+Tight:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>{css}</style>
</head>
<body>
  <header class="page-head">
    <div class="container">
      <h1>Phase 2, staging dashboard</h1>
      <p class="muted">Review and approve metadata, ratings, and hero captions for {total} parsed reviews before they go live. Photos are referenced from <code>_working/sources/</code> and will be copied to <code>assets/reviews/</code> only after approval.</p>
      <div class="stats">
        <span><b>{total}</b> reviews</span>
        <span><b>{flagged}</b> need attention</span>
        <span><b>{unresolved_cuisine}</b> cuisine unresolved</span>
        <span><b>{unresolved_suburb}</b> suburb unresolved</span>
        <span><b>{missing_ratings}</b> no ratings</span>
        <span><b>{stars_only}</b> stars-only (need conversion)</span>
        <span><b>{has_video}</b> contain video clips</span>
        <span><b>{has_heic}</b> contain HEIC photos</span>
      </div>
      <div class="legend">
        <b>Proposed new cuisine buckets:</b> {legend_new_cuisines}<br>
        <b>Proposed new suburb buckets:</b> {legend_new_suburbs}<br>
        <span class="muted">Existing cuisines: {", ".join(esc(c) for c in d["existing_cuisine_buckets"])}. Existing suburbs: {", ".join(esc(s) for s in d["existing_suburb_buckets"])}. Generated {esc(generated)}.</span>
      </div>
    </div>
  </header>

  <div class="container">
    <div class="filter-bar">
      <span class="filter-group-label">Show</span>
      <button data-filter="attention" data-value="all" class="is-active">All</button>
      <button data-filter="attention" data-value="flagged">Needs attention</button>
      <button data-filter="attention" data-value="clean">Clean</button>

      <span class="filter-group-label">Ratings</span>
      <button data-filter="ratings" data-value="all" class="is-active">All</button>
      <button data-filter="ratings" data-value="json-native">Native</button>
      <button data-filter="ratings" data-value="caption-parsed">Parsed</button>
      <button data-filter="ratings" data-value="stars-only">Stars only</button>
      <button data-filter="ratings" data-value="missing">Missing</button>

      <span class="filter-group-label">Cuisine</span>
      <select data-filter="cuisine"><option value="all">All</option>{cuisine_options}</select>
      <span class="filter-group-label">Suburb</span>
      <select data-filter="suburb"><option value="all">All</option>{suburb_options}</select>

      <span class="muted" style="margin-left:auto"><b><span id="visible-count">{total}</span></b> visible</span>
    </div>

    {cards}
  </div>

  <script>{js}</script>
</body>
</html>
"""

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(doc)
    print(f"Wrote staging dashboard to {OUT}")


if __name__ == "__main__":
    main()
