#!/usr/bin/env python3
"""Interactive staging dashboard, v2.

Renders every parsed review as an editable card. All edits are auto-saved to
the browser's localStorage (key: slf-staging-v2) so progress survives a page
close. An 'Export changes' button writes a JSON file containing every edited
field, which Sasenka hands back to the assistant for application to the live
site.

Generates: _working/staging.html (overwrites the v1 read-only version).
"""
import html
import json
import os

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


def render_flags(flags):
    if not flags:
        return ""
    chips = []
    for f in flags:
        label = FLAG_LABELS.get(f, f)
        chips.append(f'<span class="flag" data-flag="{esc(f)}">{esc(label)}</span>')
    return f'<div class="flags">{"".join(chips)}</div>'


def render_stars(stars):
    if not stars:
        return ""
    parts = []
    for k, v in stars.items():
        parts.append(
            f'<span class="pill pill-star"><span class="pill-label">{esc(k.title())}</span>'
            f'<span class="pill-value">{"★" * v}</span></span>'
        )
    return f'<div class="stars-note"><span class="muted">Source stars:</span> {"".join(parts)}</div>'


def render_photos(r, editable=True):
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
        order = p.get("order")
        hero_radio = (
            f'<label class="hero-choose" title="Set as hero photo">'
            f'<input type="radio" name="hero__{esc(slug)}" value="{esc(fn)}" data-field="hero_photo">'
            f'<span>hero</span></label>'
            if not (is_video or is_heic) else ""
        )
        if is_video:
            media = f'<div class="photo-placeholder">video<br><code>{esc(fn)}</code></div>'
        elif is_heic:
            media = f'<div class="photo-placeholder">HEIC<br><code>{esc(fn)}</code><br><span class="muted">browser can\'t render</span></div>'
        else:
            media = f'<img loading="lazy" src="{esc(src)}" alt="">'
        cap_field = (
            f'<input class="photo-caption-input" data-field="photo_caption" data-order="{esc(order)}" '
            f'value="{esc(cap)}" placeholder="caption (order {esc(order)})">'
        )
        cards.append(
            f'<figure class="photo-card">{media}'
            f'<figcaption><span class="photo-order">{esc(order)}</span>'
            f'{cap_field}{hero_radio}</figcaption></figure>'
        )
    return f'<div class="photo-grid">{"".join(cards)}</div>'


def render_hashtags(tags):
    if not tags:
        return ""
    chips = [f'<span class="hash">#{esc(t)}</span>' for t in tags[:12]]
    extra = f' <span class="muted">+{len(tags) - 12} more</span>' if len(tags) > 12 else ""
    return f'<div class="hashtags">{"".join(chips)}{extra}</div>'


def select_options(current, existing, proposed_new):
    """Return <option> HTML for a bucket <select>, grouped."""
    parts = ['<option value="">(unresolved)</option>']
    if existing:
        parts.append('<optgroup label="Existing">')
        for b in sorted(existing):
            sel = " selected" if current == b else ""
            parts.append(f'<option value="{esc(b)}"{sel}>{esc(b)}</option>')
        parts.append("</optgroup>")
    if proposed_new:
        parts.append('<optgroup label="Newly proposed">')
        for b in sorted(proposed_new):
            sel = " selected" if current == b else ""
            parts.append(f'<option value="{esc(b)}"{sel}>{esc(b)}</option>')
        parts.append("</optgroup>")
    parts.append('<option value="__custom__">+ custom bucket...</option>')
    return "".join(parts)


def card(r, existing_cuisines, proposed_cuisines, existing_suburbs, proposed_suburbs):
    slug = r["slug"]
    date = (r.get("date_iso") or "")[:10]
    name = r.get("restaurant_name") or ""
    handle = r.get("instagram_handle") or ""
    flag_attrs = " ".join(f'flag-{f}' for f in (r.get("flags") or []))
    attn = "attn" if r.get("flags") else ""

    hero_photo = None
    hero_is_heic = False
    for p in r.get("photos") or []:
        if not p.get("is_video") and not p["filename"].lower().endswith(".heic"):
            hero_photo = p["filename"]
            break
        if not p.get("is_video") and p["filename"].lower().endswith(".heic") and hero_photo is None:
            hero_photo = p["filename"]
            hero_is_heic = True

    hero_src = f'sources/food_reviews/{slug}/photos/{hero_photo}' if hero_photo and not hero_is_heic else ""
    if hero_src:
        hero_block = f'<div class="hero-photo"><img loading="lazy" src="{esc(hero_src)}" alt="" data-hero-img></div>'
    elif hero_is_heic:
        hero_block = f'<div class="hero-photo hero-empty">hero is HEIC<br><code>{esc(hero_photo)}</code></div>'
    else:
        hero_block = '<div class="hero-photo hero-empty">no hero photo</div>'

    r_vals = r.get("ratings") or {}
    def score_input(key):
        v = r_vals.get(key) if r_vals else ""
        v = "" if v is None else v
        return (
            f'<label class="score-input"><span class="score-label">{key.replace("_", " ").replace("would i ", "").title()}</span>'
            f'<input type="number" min="0" max="10" step="0.5" data-field="score_{key}" value="{esc(v)}" placeholder="?"></label>'
        )
    scores_html = "".join(score_input(k) for k in ["comfort", "soul", "mastery", "taste", "would_i_die_happy"])

    src_class = {
        "json-native": "badge-ok",
        "caption-parsed": "badge-ok",
        "stars-only": "badge-warn",
        "missing": "badge-miss",
    }.get(r["ratings_source"], "badge-warn")
    ratings_badge = f'<span class="badge {src_class}" title="Source of the pre-filled scores">{esc(r["ratings_source"])}</span>'

    cuisine_current = r["cuisine"]["bucket"] or ""
    suburb_current = r["suburb"]["bucket"] or ""

    cuisine_select = select_options(cuisine_current, existing_cuisines, proposed_cuisines)
    suburb_select = select_options(suburb_current, existing_suburbs, proposed_suburbs)

    hero_caption = r.get("proposed_hero_caption") or ""
    standfirst = r.get("standfirst_seed_from_source") or ""
    caption_clean = r.get("caption_clean") or ""

    return f'''
<article class="review-card {attn} {flag_attrs}" id="{esc(slug)}" data-slug="{esc(slug)}" data-cuisine="{esc(cuisine_current or '')}" data-suburb="{esc(suburb_current or '')}" data-ratings="{esc(r["ratings_source"])}">
  <header class="card-head">
    <div class="card-head__left">
      {hero_block}
      <div class="include-toggle" role="radiogroup" aria-label="Include in archive">
        <label><input type="radio" name="include__{esc(slug)}" value="include" data-field="include_status" checked><span>Include</span></label>
        <label><input type="radio" name="include__{esc(slug)}" value="notes" data-field="include_status"><span>Notes only</span></label>
        <label><input type="radio" name="include__{esc(slug)}" value="exclude" data-field="include_status"><span>Exclude</span></label>
      </div>
    </div>
    <div class="card-head__right">
      <div class="card-title-row">
        <div class="title-fields">
          <span class="eyebrow">{esc(date)} &middot; review #{esc(r.get("order"))}</span>
          <label class="big-input">Restaurant name
            <input type="text" data-field="restaurant_name" value="{esc(name)}" placeholder="Restaurant name">
          </label>
          <label class="mid-input">Instagram handle
            <input type="text" data-field="instagram_handle" value="{esc(handle)}" placeholder="@handle">
          </label>
        </div>
        <div class="title-aside">
          {render_flags(r.get("flags") or [])}
          <div class="card-status">
            <label class="reviewed-toggle"><input type="checkbox" data-field="reviewed"> <span>Mark reviewed</span></label>
            <span class="edit-badge" hidden>edited</span>
          </div>
        </div>
      </div>

      <div class="meta-edit">
        <label class="select-input">Cuisine
          <select data-field="cuisine_bucket">{cuisine_select}</select>
          <input type="text" class="custom-input" data-field="cuisine_bucket_custom" placeholder="type custom bucket" hidden>
        </label>
        <label class="select-input">Suburb / area
          <select data-field="suburb_bucket">{suburb_select}</select>
          <input type="text" class="custom-input" data-field="suburb_bucket_custom" placeholder="type custom bucket" hidden>
        </label>
        <div class="slug-line">Slug: <code>{esc(slug)}</code></div>
      </div>

      <div class="scores-block">
        <div class="scores-head">Five scores {ratings_badge}</div>
        <div class="scores-row">{scores_html}</div>
        {render_stars(r.get("star_ratings"))}
      </div>

      <label class="full-input">Proposed hero caption (shown on hero image)
        <input type="text" data-field="hero_caption" value="{esc(hero_caption)}" placeholder="Hero caption">
      </label>
      <label class="full-input">Standfirst (1-2 lines, shown under the title)
        <textarea data-field="standfirst" rows="2" placeholder="Standfirst line, in site voice">{esc(standfirst)}</textarea>
      </label>
      <label class="full-input">Private notes (not published)
        <textarea data-field="notes" rows="2" placeholder="Notes to yourself"></textarea>
      </label>
    </div>
  </header>

  <details class="caption-full">
    <summary>Show full source caption (read-only)</summary>
    <pre>{esc(caption_clean)}</pre>
  </details>

  <details class="photos-toggle" open>
    <summary>Photos ({esc(len(r.get("photos") or []))}) — pick hero via the 'hero' tick, tweak any caption inline</summary>
    {render_photos(r)}
  </details>

  {render_hashtags(r.get("hashtags"))}
</article>
'''


def main():
    with open(DATASET, "r", encoding="utf-8") as fh:
        d = json.load(fh)

    reviews = d["reviews"]
    generated = d.get("generated_at", "")

    existing_cuisines = set(d.get("existing_cuisine_buckets") or [])
    proposed_cuisines = set(d.get("proposed_new_cuisine_buckets") or [])
    existing_suburbs = set(d.get("existing_suburb_buckets") or [])
    proposed_suburbs = set(d.get("proposed_new_suburb_buckets") or [])

    total = len(reviews)
    flagged = sum(1 for r in reviews if r.get("flags"))
    unresolved_cuisine = sum(1 for r in reviews if not r["cuisine"]["bucket"])
    unresolved_suburb = sum(1 for r in reviews if not r["suburb"]["bucket"])
    missing_ratings = sum(1 for r in reviews if r["ratings_source"] == "missing")
    stars_only = sum(1 for r in reviews if r["ratings_source"] == "stars-only")
    has_video = sum(1 for r in reviews if any(p.get("is_video") for p in (r.get("photos") or [])))
    has_heic = sum(1 for r in reviews if "heic-photos" in (r.get("flags") or []))

    cards = "\n".join(
        card(r, existing_cuisines, proposed_cuisines, existing_suburbs, proposed_suburbs)
        for r in reviews
    )

    # Pass the list of slugs + initial proposals into the JS for sanity checks.
    initial_state = {
        r["slug"]: {
            "restaurant_name": r.get("restaurant_name") or "",
            "instagram_handle": r.get("instagram_handle") or "",
            "cuisine_bucket": r["cuisine"]["bucket"] or "",
            "suburb_bucket": r["suburb"]["bucket"] or "",
            "hero_caption": r.get("proposed_hero_caption") or "",
            "standfirst": r.get("standfirst_seed_from_source") or "",
            "ratings_source": r["ratings_source"],
            "scores": r.get("ratings") or {},
            "hero_photo": next(
                (p["filename"] for p in r.get("photos") or []
                 if not p.get("is_video") and not p["filename"].lower().endswith(".heic")),
                ""),
        }
        for r in reviews
    }

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
code{font-family:'JetBrains Mono', ui-monospace, Menlo, monospace; font-size:12px; background:var(--warm-cream); padding:1px 5px; border-radius:3px}
.muted{color:var(--ink-soft)}
.italic{font-family:'Instrument Serif', serif; font-style:italic}

.container{max-width:1240px;margin:0 auto;padding:0 24px}
header.page-head{background:var(--paper);border-bottom:1px solid var(--rule);padding:24px 0 14px}
h1{font-family:'Archivo Black', Arial Black, Impact, sans-serif; letter-spacing:-1px; margin:0 0 4px; font-size:30px}
.eyebrow{text-transform:uppercase;letter-spacing:.1em;font-size:11px;color:var(--ink-soft);font-weight:600; display:block; margin-bottom:2px}

.stats{display:flex; gap:16px; flex-wrap:wrap; margin-top:10px; font-size:13px; color:var(--ink-muted)}
.stats b{color:var(--ink)}

.toolbar{position:sticky; top:0; z-index:20; background:var(--cream); padding:12px 0 10px; border-bottom:1px solid var(--rule-soft)}
.toolbar-row{display:flex; gap:10px; flex-wrap:wrap; align-items:center}
.toolbar .filter-group-label{font-size:11px; color:var(--ink-soft); text-transform:uppercase; letter-spacing:.08em; margin-right:2px}
.toolbar button{font:inherit; background:var(--paper); border:1px solid var(--rule); color:var(--ink); padding:6px 12px; border-radius:999px; cursor:pointer}
.toolbar button.is-active{background:var(--ink); color:var(--paper); border-color:var(--ink)}
.toolbar button.primary{background:var(--olive); color:#fff; border-color:var(--olive); font-weight:600}
.toolbar button.danger{border-color:var(--tomato); color:var(--tomato)}
.toolbar button.danger:hover{background:var(--tomato); color:#fff}
.toolbar select{font:inherit; background:var(--paper); border:1px solid var(--rule); padding:6px 10px; border-radius:6px}
.progress-bar{flex:0 0 auto; display:flex; align-items:center; gap:8px; font-size:12px; color:var(--ink-muted)}
.progress-track{width:160px; height:8px; background:var(--warm-cream); border-radius:4px; overflow:hidden}
.progress-fill{height:100%; background:var(--olive); width:0%; transition:width .15s}
.save-status{font-size:12px; color:var(--ink-soft); margin-left:auto}

.review-card{background:var(--paper); border:1px solid var(--rule); border-radius:10px; padding:18px; margin:16px 0; box-shadow:0 1px 0 rgba(0,0,0,.02); scroll-margin-top:80px}
.review-card.attn{border-left:4px solid var(--tomato)}
.review-card.reviewed{border-left:4px solid var(--olive); opacity:.8}
.review-card.edited{box-shadow:0 0 0 2px rgba(75,93,59,.3)}

.card-head{display:grid; grid-template-columns: 260px 1fr; gap:20px}
.card-head__left{display:flex; flex-direction:column; gap:10px}
.hero-photo{aspect-ratio:4/3; background:var(--warm-cream); border-radius:8px; overflow:hidden; position:relative}
.hero-photo img{width:100%; height:100%; object-fit:cover; display:block}
.hero-photo.hero-empty{display:flex; align-items:center; justify-content:center; color:var(--ink-soft); font-size:12px; text-align:center; padding:8px}

.include-toggle{display:flex; gap:4px; font-size:12px}
.include-toggle label{display:flex; align-items:center; gap:4px; padding:4px 8px; border:1px solid var(--rule); border-radius:6px; cursor:pointer; background:var(--paper); flex:1; justify-content:center}
.include-toggle input{margin:0}
.include-toggle input:checked + span{font-weight:700; color:var(--olive)}

.card-title-row{display:flex; justify-content:space-between; gap:14px; align-items:flex-start; margin-bottom:10px}
.title-fields{flex:1}
.title-aside{display:flex; flex-direction:column; gap:6px; align-items:flex-end}

.big-input, .mid-input, .full-input, .select-input, .score-input{display:flex; flex-direction:column; gap:2px; font-size:11px; text-transform:uppercase; letter-spacing:.06em; color:var(--ink-soft); font-weight:600}
.big-input input{font:400 22px/1.2 'Instrument Serif', serif; padding:4px 6px; border:1px solid transparent; border-bottom:1px solid var(--rule-soft); background:transparent; border-radius:4px; text-transform:none; letter-spacing:0; color:var(--ink)}
.big-input input:focus, .mid-input input:focus, .select-input select:focus, .full-input input:focus, .full-input textarea:focus, .score-input input:focus, .custom-input:focus{outline:2px solid var(--olive); outline-offset:1px; border-color:var(--olive); background:var(--paper)}
.mid-input input, .full-input input, .full-input textarea{font:inherit; padding:6px 8px; border:1px solid var(--rule); border-radius:4px; background:var(--paper); text-transform:none; letter-spacing:0; color:var(--ink)}
.select-input select{font:inherit; padding:6px 8px; border:1px solid var(--rule); border-radius:4px; background:var(--paper); text-transform:none; letter-spacing:0; color:var(--ink); min-width:160px}
.custom-input{margin-top:4px; font:inherit; padding:6px 8px; border:1px solid var(--olive); border-radius:4px; background:var(--paper); text-transform:none; letter-spacing:0}
.full-input textarea{resize:vertical; min-height:38px}

.meta-edit{display:flex; gap:16px; flex-wrap:wrap; margin:8px 0 12px; align-items:flex-end}
.slug-line{font-size:11px; color:var(--ink-soft); text-transform:uppercase; letter-spacing:.06em; margin-left:auto}

.scores-block{margin-bottom:10px}
.scores-head{font-size:11px; color:var(--ink-soft); text-transform:uppercase; letter-spacing:.06em; font-weight:600; margin-bottom:4px; display:flex; align-items:center; gap:8px}
.scores-row{display:flex; gap:6px; flex-wrap:wrap}
.score-input{flex:1; min-width:90px; background:var(--warm-cream); padding:6px 8px; border-radius:6px; gap:2px}
.score-input .score-label{color:var(--ink-muted); font-size:10px}
.score-input input{font:400 18px/1 'Instrument Serif', serif; padding:2px 4px; border:1px solid transparent; background:transparent; width:100%; text-align:left}
.stars-note{font-size:12px; margin-top:6px}

.flags{display:flex; gap:4px; flex-wrap:wrap; justify-content:flex-end}
.flag{font-size:11px; padding:2px 8px; border-radius:999px; background:#f5d6d0; color:#7a1f15; font-weight:600; text-transform:lowercase}

.badge{font-size:10px; padding:2px 7px; border-radius:999px; text-transform:uppercase; letter-spacing:.06em; font-weight:700}
.badge-ok{background:#dce8d4; color:#355429}
.badge-warn{background:#f5ddc3; color:#7a4a12}
.badge-miss{background:#f5d6d0; color:#7a1f15}

.reviewed-toggle{display:flex; align-items:center; gap:4px; font-size:12px; color:var(--ink-muted); cursor:pointer; padding:4px 8px; border:1px solid var(--rule); border-radius:6px}
.reviewed-toggle:hover{background:var(--warm-cream)}
.reviewed-toggle input:checked ~ span{color:var(--olive); font-weight:600}
.edit-badge{font-size:10px; padding:2px 8px; border-radius:999px; background:var(--olive); color:#fff; font-weight:700; text-transform:uppercase}

.pill{display:inline-flex; align-items:baseline; gap:4px; background:var(--warm-cream); padding:3px 8px; border-radius:6px; font-size:12px}
.pill-star{background:#f3e8c8}
.pill-label{color:var(--ink-soft); font-weight:600; text-transform:uppercase; letter-spacing:.06em; font-size:10px}
.pill-value{font-family:'Instrument Serif', serif; font-size:14px}

.caption-full{margin-top:10px}
.caption-full summary{cursor:pointer; color:var(--olive); font-size:12px}
.caption-full pre{margin:6px 0 0; padding:10px; background:var(--warm-cream); border-radius:6px; font-family:inherit; font-size:13px; color:var(--ink-muted); white-space:pre-wrap}

.photos-toggle{margin-top:10px; border-top:1px solid var(--rule-soft); padding-top:10px}
.photos-toggle summary{cursor:pointer; color:var(--olive); font-weight:600; font-size:13px}
.photo-grid{display:grid; grid-template-columns:repeat(auto-fill, minmax(180px, 1fr)); gap:10px; margin-top:10px}
.photo-card{margin:0; background:var(--warm-cream); border-radius:6px; overflow:hidden; display:flex; flex-direction:column}
.photo-card img{width:100%; aspect-ratio:1/1; object-fit:cover; display:block}
.photo-placeholder{aspect-ratio:1/1; display:flex; flex-direction:column; align-items:center; justify-content:center; font-size:11px; color:var(--ink-soft); padding:8px; text-align:center; background:#efe6cf; gap:4px; font-weight:600; text-transform:uppercase; letter-spacing:.08em}
.photo-card figcaption{font-size:11px; padding:6px 8px; display:flex; gap:6px; align-items:center}
.photo-order{font-weight:700; color:var(--ink); background:var(--paper); padding:0 6px; border-radius:4px; height:18px; flex-shrink:0}
.photo-caption-input{flex:1; font:400 11px/1.3 inherit; padding:3px 5px; border:1px solid transparent; border-bottom:1px solid var(--rule-soft); background:transparent; border-radius:3px}
.photo-caption-input:focus{outline:1px solid var(--olive); background:var(--paper)}
.hero-choose{font-size:10px; display:flex; align-items:center; gap:2px; cursor:pointer; flex-shrink:0; color:var(--ink-soft)}
.hero-choose input:checked ~ span{color:var(--olive); font-weight:700}

.hashtags{margin-top:10px; display:flex; flex-wrap:wrap; gap:4px}
.hash{font-size:11px; color:var(--ink-soft); background:var(--warm-cream); padding:1px 6px; border-radius:4px}

@media (max-width: 820px){
  .card-head{grid-template-columns: 1fr}
  .title-aside{align-items:flex-start}
  .progress-bar{width:100%}
}
"""

    js = """
const STORAGE_KEY = 'slf-staging-v2';

// Initial proposals, so we can tell what's been edited.
const INITIAL = __INITIAL_STATE__;

let store = {};
try { store = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}'); }
catch (e) { console.warn('corrupt store, resetting'); store = {}; }

function saveStore() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
  document.getElementById('save-status').textContent =
    `Saved locally at ${new Date().toLocaleTimeString()}`;
}

function ensureSlot(slug) {
  if (!store[slug]) store[slug] = {};
  return store[slug];
}

function isDirty(slug) {
  const slot = store[slug];
  if (!slot) return false;
  for (const k of Object.keys(slot)) {
    if (k === 'reviewed' || k === 'include_status' || k === 'notes' || k === 'photo_captions') {
      if (slot[k] && Object.keys(slot[k]).length) return true;
      if (slot[k]) return true;
    } else if (slot[k] !== undefined && slot[k] !== null && slot[k] !== '') {
      return true;
    }
  }
  return false;
}

function updateCardVisuals(card) {
  const slug = card.dataset.slug;
  card.classList.toggle('edited', isDirty(slug));
  const reviewed = store[slug]?.reviewed === true;
  card.classList.toggle('reviewed', reviewed);
  const badge = card.querySelector('.edit-badge');
  if (badge) badge.hidden = !isDirty(slug);
}

function hydrateCard(card) {
  const slug = card.dataset.slug;
  const slot = store[slug];
  if (!slot) return;
  for (const [field, value] of Object.entries(slot)) {
    if (field === 'photo_captions') {
      for (const [order, cap] of Object.entries(value || {})) {
        const el = card.querySelector(`.photo-caption-input[data-order="${order}"]`);
        if (el) el.value = cap;
      }
    } else if (field === 'hero_photo') {
      const el = card.querySelector(`input[name="hero__${slug}"][value="${CSS.escape(value)}"]`);
      if (el) el.checked = true;
      if (value) {
        const heroBox = card.querySelector('.hero-photo');
        if (heroBox) {
          heroBox.innerHTML = `<img loading="lazy" src="sources/food_reviews/${slug}/photos/${value}" alt="" data-hero-img>`;
          heroBox.classList.remove('hero-empty');
        }
      }
    } else if (field === 'include_status') {
      const el = card.querySelector(`input[name="include__${slug}"][value="${value}"]`);
      if (el) el.checked = true;
    } else if (field === 'reviewed') {
      const el = card.querySelector('[data-field="reviewed"]');
      if (el) el.checked = !!value;
    } else if (field === 'cuisine_bucket' || field === 'suburb_bucket') {
      const sel = card.querySelector(`select[data-field="${field}"]`);
      if (sel) {
        if (Array.from(sel.options).some(o => o.value === value)) {
          sel.value = value;
        } else if (value) {
          // Custom value, add a temporary option
          const opt = document.createElement('option');
          opt.value = value; opt.textContent = `${value} (custom)`; opt.dataset.custom = '1';
          sel.appendChild(opt);
          sel.value = value;
        }
      }
    } else {
      const el = card.querySelector(`[data-field="${field}"]`);
      if (el && !el.matches('input[type="radio"]')) el.value = value;
    }
  }
  updateCardVisuals(card);
}

function initCustomBucketToggle(card) {
  for (const field of ['cuisine_bucket', 'suburb_bucket']) {
    const sel = card.querySelector(`select[data-field="${field}"]`);
    const customInput = card.querySelector(`input[data-field="${field}_custom"]`);
    if (!sel || !customInput) continue;
    sel.addEventListener('change', () => {
      if (sel.value === '__custom__') {
        customInput.hidden = false;
        customInput.focus();
      } else {
        customInput.hidden = true;
        customInput.value = '';
      }
    });
    customInput.addEventListener('change', () => {
      const v = customInput.value.trim();
      if (!v) return;
      const slot = ensureSlot(card.dataset.slug);
      slot[field] = v;
      // Add as option + select it
      const opt = document.createElement('option');
      opt.value = v; opt.textContent = `${v} (custom)`; opt.dataset.custom = '1';
      sel.appendChild(opt); sel.value = v;
      customInput.hidden = true;
      saveStore();
      updateCardVisuals(card);
    });
  }
}

function captureFromCard(card, evt) {
  const slug = card.dataset.slug;
  const slot = ensureSlot(slug);
  const el = evt.target;
  const field = el.dataset.field;
  if (!field) return;
  if (field === 'photo_caption') {
    slot.photo_captions = slot.photo_captions || {};
    slot.photo_captions[el.dataset.order] = el.value;
  } else if (field === 'reviewed') {
    slot.reviewed = el.checked;
  } else if (field === 'include_status') {
    slot.include_status = el.value;
  } else if (field === 'hero_photo') {
    slot.hero_photo = el.value;
    const heroBox = card.querySelector('.hero-photo');
    if (heroBox) {
      heroBox.innerHTML = `<img loading="lazy" src="sources/food_reviews/${slug}/photos/${el.value}" alt="" data-hero-img>`;
      heroBox.classList.remove('hero-empty');
    }
  } else if (field.startsWith('score_')) {
    slot.scores = slot.scores || {};
    const key = field.slice('score_'.length);
    slot.scores[key] = el.value === '' ? null : parseFloat(el.value);
  } else if (field === 'cuisine_bucket' || field === 'suburb_bucket') {
    if (el.value === '__custom__') return; // wait for custom input
    slot[field] = el.value;
  } else {
    slot[field] = el.value;
  }
  saveStore();
  updateCardVisuals(card);
  updateProgress();
}

function updateProgress() {
  const total = document.querySelectorAll('.review-card').length;
  const reviewed = Object.values(store).filter(s => s.reviewed).length;
  const edited = document.querySelectorAll('.review-card.edited').length;
  document.getElementById('progress-reviewed').textContent = reviewed;
  document.getElementById('progress-total').textContent = total;
  document.getElementById('progress-edited').textContent = edited;
  document.getElementById('progress-fill').style.width = `${(reviewed / total) * 100}%`;
}

function filterCards() {
  const showFlagged = document.querySelector('[data-filter="attention"].is-active')?.dataset.value;
  const ratings = document.querySelector('[data-filter="ratings"].is-active')?.dataset.value;
  const cuisine = document.querySelector('select[data-filter="cuisine"]').value;
  const suburb = document.querySelector('select[data-filter="suburb"]').value;
  const reviewedFilter = document.querySelector('[data-filter="reviewed"].is-active')?.dataset.value;
  let visible = 0;
  document.querySelectorAll('.review-card').forEach(c => {
    let show = true;
    if (showFlagged === 'flagged' && !c.classList.contains('attn')) show = false;
    if (showFlagged === 'clean' && c.classList.contains('attn')) show = false;
    if (reviewedFilter === 'done' && !c.classList.contains('reviewed')) show = false;
    if (reviewedFilter === 'todo' && c.classList.contains('reviewed')) show = false;
    if (ratings !== 'all' && c.dataset.ratings !== ratings) show = false;
    if (cuisine !== 'all' && c.dataset.cuisine !== cuisine) show = false;
    if (suburb !== 'all' && c.dataset.suburb !== suburb) show = false;
    c.style.display = show ? '' : 'none';
    if (show) visible++;
  });
  document.getElementById('visible-count').textContent = visible;
}

function jumpNextUnreviewed() {
  const cards = Array.from(document.querySelectorAll('.review-card'));
  const curTop = window.scrollY;
  const next = cards.find(c => c.offsetTop > curTop + 10 && !c.classList.contains('reviewed') && c.style.display !== 'none');
  if (next) next.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function exportChanges() {
  // Only include slots with any content.
  const out = {};
  for (const [slug, slot] of Object.entries(store)) {
    if (!slot || Object.keys(slot).length === 0) continue;
    out[slug] = slot;
  }
  const payload = {
    exported_at: new Date().toISOString(),
    source_dataset: 'phase1-dataset.json',
    review_count_total: document.querySelectorAll('.review-card').length,
    review_count_edited: Object.keys(out).length,
    edits: out,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
  a.href = url;
  a.download = `phase2-edits-${ts}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

function clearLocal() {
  if (!confirm('This wipes all your local edits in this browser. The source dataset stays untouched. Continue?')) return;
  localStorage.removeItem(STORAGE_KEY);
  store = {};
  location.reload();
}

// Wire up
document.querySelectorAll('.review-card').forEach(c => {
  hydrateCard(c);
  initCustomBucketToggle(c);
  c.addEventListener('input', e => captureFromCard(c, e));
  c.addEventListener('change', e => captureFromCard(c, e));
});

document.addEventListener('click', e => {
  const b = e.target.closest('[data-filter]');
  if (b && b.tagName === 'BUTTON') {
    const group = b.dataset.filter;
    document.querySelectorAll(`button[data-filter="${group}"]`).forEach(x => x.classList.toggle('is-active', x === b));
    filterCards();
  }
});
document.addEventListener('change', e => {
  if (e.target.matches('select[data-filter]')) filterCards();
});

document.getElementById('export-btn').addEventListener('click', exportChanges);
document.getElementById('clear-btn').addEventListener('click', clearLocal);
document.getElementById('next-btn').addEventListener('click', jumpNextUnreviewed);

updateProgress();
filterCards();
document.getElementById('save-status').textContent = Object.keys(store).length ? 'Local edits restored' : 'No local edits yet';
"""

    js = js.replace("__INITIAL_STATE__", json.dumps(initial_state))

    # Filter options
    cuisine_opts = sorted({r["cuisine"]["bucket"] for r in reviews if r["cuisine"]["bucket"]})
    suburb_opts = sorted({r["suburb"]["bucket"] for r in reviews if r["suburb"]["bucket"]})
    cuisine_options = "".join(f'<option value="{esc(c)}">{esc(c)}</option>' for c in cuisine_opts)
    suburb_options = "".join(f'<option value="{esc(s)}">{esc(s)}</option>' for s in suburb_opts)

    doc = f"""<!doctype html>
<html lang="en-GB">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Phase 2 staging — Sasenka Loves Food</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Archivo+Black&family=Instrument+Serif:ital@0;1&family=Inter+Tight:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>{css}</style>
</head>
<body>
  <header class="page-head">
    <div class="container">
      <h1>Phase 2, staging dashboard</h1>
      <p class="muted">Review {total} parsed reviews. Every edit is auto-saved in your browser (localStorage). When you're done, click <b>Export changes</b> to download a JSON file: send that back to me and I'll apply it to the live site. Nothing here touches the live archive yet.</p>
      <div class="stats">
        <span><b>{total}</b> reviews</span>
        <span><b>{flagged}</b> need attention</span>
        <span><b>{unresolved_cuisine}</b> cuisine unresolved</span>
        <span><b>{unresolved_suburb}</b> suburb unresolved</span>
        <span><b>{missing_ratings}</b> no ratings</span>
        <span><b>{stars_only}</b> stars-only (need conversion)</span>
        <span><b>{has_video}</b> contain video</span>
        <span><b>{has_heic}</b> contain HEIC</span>
      </div>
    </div>
  </header>

  <div class="container">
    <div class="toolbar">
      <div class="toolbar-row">
        <span class="filter-group-label">Show</span>
        <button data-filter="attention" data-value="all" class="is-active">All</button>
        <button data-filter="attention" data-value="flagged">Needs attention</button>
        <button data-filter="attention" data-value="clean">Clean</button>

        <span class="filter-group-label">Reviewed</span>
        <button data-filter="reviewed" data-value="all" class="is-active">All</button>
        <button data-filter="reviewed" data-value="todo">To do</button>
        <button data-filter="reviewed" data-value="done">Done</button>

        <span class="filter-group-label">Ratings</span>
        <button data-filter="ratings" data-value="all" class="is-active">All</button>
        <button data-filter="ratings" data-value="json-native">Native</button>
        <button data-filter="ratings" data-value="caption-parsed">Parsed</button>
        <button data-filter="ratings" data-value="stars-only">Stars</button>
        <button data-filter="ratings" data-value="missing">Missing</button>

        <span class="filter-group-label">Cuisine</span>
        <select data-filter="cuisine"><option value="all">All</option>{cuisine_options}</select>
        <span class="filter-group-label">Suburb</span>
        <select data-filter="suburb"><option value="all">All</option>{suburb_options}</select>

        <span class="muted" style="margin-left:auto"><b><span id="visible-count">{total}</span></b> visible</span>
      </div>
      <div class="toolbar-row" style="margin-top:8px">
        <button id="next-btn">Jump to next un-reviewed ↓</button>
        <div class="progress-bar">
          <span>Reviewed <b><span id="progress-reviewed">0</span></b>/<span id="progress-total">{total}</span></span>
          <div class="progress-track"><div class="progress-fill" id="progress-fill"></div></div>
          <span>Edited <b><span id="progress-edited">0</span></b></span>
        </div>
        <button id="export-btn" class="primary">Export changes ↓</button>
        <button id="clear-btn" class="danger">Clear local edits</button>
        <span class="save-status" id="save-status">&nbsp;</span>
      </div>
    </div>

    {cards}

    <div style="padding:30px 0; text-align:center">
      <button id="export-btn-2" class="primary" onclick="document.getElementById('export-btn').click()">Export changes ↓</button>
    </div>
  </div>

  <script>{js}</script>
</body>
</html>
"""

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(doc)
    print(f"Wrote interactive staging dashboard to {OUT}")
    print(f"Size: {os.path.getsize(OUT)} bytes")


if __name__ == "__main__":
    main()
