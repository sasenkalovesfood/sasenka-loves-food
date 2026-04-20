#!/usr/bin/env python3
"""Deduplicate reviews-archive.html after the Phase 3 build was run twice.

Removes all month-group sections for months 2025-06 through 2026-04 (which
were added by Phase 3), removes any May 2025 cards whose slug is in the
phase2 dataset (the prepended new cards), and removes duplicate filter
chips (keeping the first occurrence).
"""
import json
import os
import re
from datetime import datetime

ROOT = "/sessions/kind-eloquent-meitner/mnt/SLF/sasenka-loves-food"
ARCHIVE = os.path.join(ROOT, "reviews-archive.html")
DATA = os.path.join(ROOT, "_working", "phase2-final.json")


def pascal_name(name):
    parts = re.split(r"[\s\-_/]+", name or "")
    pieces = []
    for p in parts:
        p = re.sub(r"[^A-Za-z0-9]", "", p)
        if p:
            pieces.append(p[:1].upper() + p[1:])
    return "".join(pieces) or "Review"


def html_filename(r):
    dt = datetime.fromisoformat(r["date_iso"].replace("Z", ""))
    return f"{dt.strftime('%Y%m%d')}-{pascal_name(r['restaurant_name'])}.html"


def main():
    with open(DATA) as f:
        data = json.load(f)
    phase2_files = {html_filename(r) for r in data["reviews"]}
    # File names of only those in May 2025
    phase2_may_files = {html_filename(r) for r in data["reviews"] if r["date_iso"][:7] == "2025-05"}

    with open(ARCHIVE, "r", encoding="utf-8") as f:
        src = f.read()

    # 1. Delete ALL month-group sections for 2025-06 through 2026-04.
    #    Pattern: from "<!-- Month Year -->\n        <section class=..." up through "</section>\n\n"
    # But the comment might or might not exist, so safer to just match <section>...</section>.
    to_remove_months = set()
    for r in data["reviews"]:
        m = r["date_iso"][:7]
        if m != "2025-05":
            to_remove_months.add(m)

    # Match the preceding HTML comment + blank lines + section up to </section>
    # Using an iterative approach:
    for month in sorted(to_remove_months, reverse=True):
        pattern = re.compile(
            r"(?:\n\s*<!--[^\n]*-->\s*\n)?\s*<section class=\"month-group\" data-month=\""
            + re.escape(month)
            + r"\">[\s\S]*?</section>\s*\n",
            re.MULTILINE,
        )
        # Remove all occurrences
        before = len(src)
        src = pattern.sub("\n", src)
        after = len(src)
        print(f"removed {month}: trimmed {before - after} chars")

    # 2. In May 2025 section, remove phase2-may cards (which were prepended twice).
    # Find May 2025 section block.
    may_match = re.search(
        r'(<section class="month-group" data-month="2025-05">)([\s\S]*?)(</section>)',
        src,
    )
    if may_match:
        may_block = may_match.group(2)
        # Remove any <a class="review-card archive-card" href="reviews/XXX"... </a> whose href
        # matches phase2_may_files. Do this twice to catch both grid + list card blocks.
        def strip_phase2_cards(block):
            # Strip all cards whose href is in phase2_may_files
            def replace_card(m):
                inner = m.group(0)
                href_m = re.search(r'href="reviews/([^"]+)"', inner)
                if href_m and href_m.group(1) in phase2_may_files:
                    return ""
                return inner

            block = re.sub(
                r'\s*<a class="review-card archive-card"[\s\S]*?</a>\n',
                replace_card,
                block,
            )
            block = re.sub(
                r'\s*<a class="archive-row archive-card"[\s\S]*?</a>\n',
                replace_card,
                block,
            )
            return block

        new_may_block = strip_phase2_cards(may_block)
        src = src[: may_match.start(2)] + new_may_block + src[may_match.end(2):]
        print("stripped phase2 may-2025 cards from existing May section")

    # 3. Deduplicate filter chips. Keep first instance only.
    def dedupe_chips(src_text, role):
        # Get the chip-row block
        pattern = re.compile(
            r'(<div class="chip-row" role="group" aria-label="'
            + re.escape(role)
            + r'">)(.*?)(</div>)',
            re.DOTALL,
        )
        m = pattern.search(src_text)
        if not m:
            return src_text
        inner = m.group(2)
        # Find chips by data-filter and keep first only
        seen = set()
        def replace_chip(cm):
            filt = cm.group(1)
            if filt in seen:
                return ""
            seen.add(filt)
            return cm.group(0)

        # Match chip buttons and dedupe
        chip_pattern = re.compile(
            r'<button type="button" class="chip[^"]*" data-category="[^"]+" data-filter="([^"]+)">[^<]*</button>\s*\n?\s*',
        )
        new_inner = chip_pattern.sub(replace_chip, inner)
        return src_text[: m.start(2)] + new_inner + src_text[m.end(2):]

    src = dedupe_chips(src, "Cuisine")
    src = dedupe_chips(src, "Suburb")
    print("deduplicated cuisine + suburb chips")

    # Tidy consecutive blank lines
    src = re.sub(r"\n{3,}", "\n\n", src)

    with open(ARCHIVE, "w", encoding="utf-8") as f:
        f.write(src)

    # Verify
    months = re.findall(r'data-month="([^"]+)"', src)
    from collections import Counter
    c = Counter(months)
    print(f"Final month-group counts: {c}")


if __name__ == "__main__":
    main()
