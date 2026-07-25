"""
Runs factlink_scraper.py once per category in CATEGORIES, back to back, and
prints a consolidated per-category summary at the end.

Usage:
    python scrapers/run_categories.py
"""

import json
import os
import random
import subprocess
import sys
import time

# Category labels can contain non-ASCII characters (fullwidth punctuation,
# Vietnamese/Japanese text); Windows' default console/redirect encoding
# (cp1252) can't print those, so force UTF-8 explicitly.
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

CATEGORIES = [
    "Surface Treatment：Heat Treatment, Plating",
    "Painting, Coating material",
]

SUMMARY_PATH = os.path.join("data", "factlink_last_run_summary.json")
BETWEEN_CATEGORY_MIN_DELAY = 2.0
BETWEEN_CATEGORY_MAX_DELAY = 3.0

SCRAPER_PATH = os.path.join(os.path.dirname(__file__), "factlink_scraper.py")


def run_category(label):
    print(f"\n{'=' * 60}\nStarting category: {label}\n{'=' * 60}")
    result = subprocess.run(
        [sys.executable, SCRAPER_PATH, "--category-label", label],
        check=False,
    )
    if result.returncode != 0:
        print(f"WARNING: scraper exited with code {result.returncode} for {label!r}")
        return None
    if not os.path.exists(SUMMARY_PATH):
        print(f"WARNING: no summary file found after running {label!r}")
        return None
    with open(SUMMARY_PATH, encoding="utf-8") as f:
        return json.load(f)


def main():
    results = []
    for i, label in enumerate(CATEGORIES):
        summary = run_category(label)
        results.append((label, summary))
        if i < len(CATEGORIES) - 1:
            time.sleep(random.uniform(BETWEEN_CATEGORY_MIN_DELAY, BETWEEN_CATEGORY_MAX_DELAY))

    print(f"\n{'=' * 60}\nBatch summary\n{'=' * 60}")
    header = f"{'Category':<50} {'Found':>6} {'New':>6} {'Updated':>8} {'Failed':>7}"
    print(header)
    print("-" * len(header))
    for label, summary in results:
        if summary is None:
            print(f"{label:<50} {'FAILED TO RUN':>30}")
            continue
        print(
            f"{label:<50} {summary['companies_discovered']:>6} "
            f"{summary['inserted']:>6} {summary['updated']:>8} {summary['failed']:>7}"
        )


if __name__ == "__main__":
    main()
