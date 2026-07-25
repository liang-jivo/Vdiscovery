"""
Fetches the FACT-LINK Vietnam homepage and extracts every category's
label -> id mapping from its search_category.php?id=NNN links, saving the
result to data/factlink_categories.json.

Run this once to (re)generate the category index; factlink_scraper.py's
--category-label lookup reads from the file it produces.
"""

import json
import os
import re
import sys

import requests

# Category labels can contain non-ASCII text (fullwidth punctuation); Windows'
# default console/redirect encoding (cp1252) can't print those, so force UTF-8.
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

BASE_URL = "https://www.fact-link.com.vn/"
OUTPUT_PATH = os.path.join("data", "factlink_categories.json")
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Matches e.g. <a href="search_category.php?id=012&amp;start=0">Plastic Injection (178)</a>
CATEGORY_LINK_RE = re.compile(
    r'<a href="search_category\.php\?id=(\d+)&(?:amp;)?start=0">([^<]+)</a>'
)


def fetch_categories():
    resp = requests.get(BASE_URL, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    categories = {}
    for cat_id, raw_label in CATEGORY_LINK_RE.findall(resp.text):
        label = re.sub(r"\s*\(\d+\)\s*$", "", raw_label).strip()
        categories[label] = cat_id
    return categories


def main():
    categories = fetch_categories()
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(categories, f, ensure_ascii=False, indent=2, sort_keys=True)
    print(f"Saved {len(categories)} categories to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
