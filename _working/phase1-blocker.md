# Phase 1, blocker note

**Status:** stopped, no dataset produced.
**Run:** automated (scheduled task), 19 April 2026.

## What happened

The task is to parse 64 remaining source reviews into a working dataset. Before parsing, I searched the filesystem for those sources. I could not find them. Per the task's own instruction ("If you cannot find them, stop and write a short note to the output folder explaining where you looked and what you found"), I stopped and wrote this note.

No JSON was written. No photos were copied. No site files were edited. The only file created in this run is this note, inside `_working/`.

## Where I looked

The site is mounted into this session at `/sessions/pensive-gracious-mendel/mnt/SLF/sasenka-loves-food/`. This is the same folder the task file refers to (it named the site path under a different session id, but the content matches: the 8 imported reviews, the archive, the assets tree, PLATFORM-GUIDE.md, etc. all line up).

I searched:

1. The site root: `/sessions/pensive-gracious-mendel/mnt/SLF/sasenka-loves-food/`
   - Contains: `index.html`, `about.html`, `rating-system.html`, `reviews-archive.html`, `headline-preview.html`, `ig-button-preview.html`, `PLATFORM-GUIDE.md`, the `reviews/` folder (the 8 imported HTML reviews plus `_template.html`), and the `assets/` folder (photos for the 8 imported reviews only).
   - No `review.json`, no per-review source folder beyond the 8 already imported, no `captions.txt`, no Instagram export, no CSV.

2. The uploads folder: `/sessions/pensive-gracious-mendel/mnt/uploads/`
   - Contains only two files: `SKILL.md` (the Phase 1 instructions themselves) and `Sasenka Loves Food - Brand Deck _offline_.html`.
   - No review sources.

3. The other SLF subtree: nothing else is mounted. Top-level `/sessions/pensive-gracious-mendel/mnt/SLF/` contains only `sasenka-loves-food/`.

4. Broader filesystem search: I ran recursive searches for filenames like `review*`, `caption*`, `source*`, `raw*`, `import*`, `instagram*`, and for all `*.json` files. The only JSON hits are internal `.claude/` session and task files. No review source data anywhere.

5. The task file references `/sessions/kind-eloquent-meitner/mnt/SLF/` and `/sessions/kind-eloquent-meitner/mnt/uploads/` as likely source locations. That session directory exists on disk but is not readable from this session (`drwxr-x---`, owned by a different user). It is possible the 64 sources are sitting inside that session's uploads area and were never mounted into this session, or were never uploaded at all.

## What I did not do

I did not parse anything. I did not write `phase1-dataset.json` or `phase1-summary.md`, because there is no source material to derive them from, and the task is explicit about not inventing content. I did not touch any file under `sasenka-loves-food/` other than creating the `_working/` folder and this note inside it.

## Suggested next step for the user

Drop the 64 source files into `/mnt/SLF/sasenka-loves-food/_working/sources/` (or into the uploads area) and re-run the scheduled task. A folder-per-review layout works well, e.g.:

```
_working/sources/
  2025-05-10_somerestaurant/
    review.json              (restaurant name, date, suburb, cuisine, IG handle)
    captions.txt             (one caption per line, in order, first line = hero)
    01_<id>.jpg, 02_<id>.jpg, ...
```

A single combined JSON or CSV with all 64 reviews would also work, as long as each record carries at minimum: restaurant name, visit date, suburb, cuisine, Instagram handle (optional), an ordered list of photo filenames, and the raw caption text for each photo. Without the raw captions the standfirst and hero caption cannot be drafted faithfully.

If the sources are already somewhere on your computer but were not selected into Cowork's working folder, pointing Cowork at that folder (so it appears under `/mnt/`) is the quickest unblock.
