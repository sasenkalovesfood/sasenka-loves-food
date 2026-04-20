# Sasenka's food reviews

This folder contains 72 food posts extracted from Sasenka's Instagram export, ordered newest first.

## Structure

- `index.xlsx` : master index, one row per review (sortable / filterable).
- One folder per review, named `YYYY-MM-DD_restaurant/`, each containing:
    - `review.md` : human-readable caption, date, ratings, photo list.
    - `review.json` : structured metadata (date, restaurant, mentions, hashtags, ratings, caption, media list). Use this when asking Claude to build a review page, it has everything already parsed.
    - `photos/` : the images and any videos from the post, numbered in original Instagram order (`01_…jpg`, `02_…jpg`, …).

## How to use with Claude

To create a review page for a single restaurant, point Claude at that folder, for example:

> "Build a polished review page for `food_reviews/2026-04-09_auntyonwandoo/`. Use `review.json` for the data and include the photos from the `photos/` subfolder."

The JSON already has restaurant name, date, ratings, hashtags, mentions, ordered media list and the full caption, so Claude can lay out a review without having to re-parse the Instagram caption.

## Notes on scope

- All 72 food posts from the export are included.
- 69 of 72 use the `#SasenkaLovesFood` tag; the other 3 are clearly food (a year-end round-up, an Attimi degustation review, and a Sri Lankan home-cooked meal), so they're included too.
- Reels have been excluded (they live under `media/reels/` in the original export, not in `posts_1.html`).
- A small number of posts contain short in-frame video clips alongside photos; those are included in `photos/` with `.mp4` extensions.
