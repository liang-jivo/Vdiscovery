"""
Scrapes the FMM (Federation of Malaysian Manufacturers) online member list
into the staging_fmm Postgres table.

Usage:
    python scrapers/fmm_scraper.py                  # full run, all pages
    python scrapers/fmm_scraper.py --max-pages 3     # test run, first N pages only

Site notes (learned by probing the live site):
- https://www.fmm.org.my/Member/MemberList?keyword=&type=Product&page=N is a
  Blazor Server app, but the member list is server-prerendered: a plain GET
  returns the fully rendered HTML (no headless browser/JS execution needed).
- Each company is a `div.vstack` containing a `.company-name` (raw name with
  the registration number embedded in trailing parens) and a `.contact-section`
  with 0-3 `.contact-info` divs, disambiguated by icon class:
    bi-telephone-fill -> phone, bi-geo-alt -> address, bi-globe -> website.
  The website's `<a href>` is always a clean absolute URL even when the
  visible text is a bare domain, so we always read the href, never the text.
- No per-company detail page/link exists anywhere in the raw HTML (the name
  is a plain `<button type="button">`, not a link) -- registration_no is the
  only available unique key, matching the brief.
- The pagination widget on page 1 shows the last page number directly
  (e.g. "268"); we parse that, but also fall back to stopping once a page
  yields zero company rows, in case the real count drifts.
- Company name format embeds the registration number in trailing parens,
  e.g. "004 International (MY) Sdn Bhd (201701036819 (1250990-V))" or
  "2M Furniture Manufacturing Sdn Bhd (1015458-A)". Some company names
  legitimately contain their own parenthetical text earlier in the string
  (e.g. "A Clouet (Malaysia) Sdn Bhd (03409-V)") -- only the LAST balanced
  parenthetical group, and only if its content starts with a digit, is
  treated as the registration number.
"""

import argparse
import json
import logging
import os
import random
import re
import sys
import time

import psycopg2
import psycopg2.extras
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
from factlink_scraper import strip_nul_bytes  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

BASE_URL = "https://www.fmm.org.my/Member/MemberList"
SOURCE_SITE = "fmm-malaysia"
MIN_DELAY_SECONDS = 2.0
MAX_DELAY_SECONDS = 3.0
RAW_HTML_DIR = os.path.join("data", "fmm_raw")
SUMMARY_PATH = os.path.join("data", "fmm_last_run_summary.json")
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("fmm_scraper")


def sleep_politely():
    time.sleep(random.uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS))


def fetch_page(session, page_num):
    resp = session.get(BASE_URL, params={"keyword": "", "type": "Product", "page": page_num}, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_total_pages(html):
    """Read the last page number off the pagination widget (e.g. the '268' in
    a run of page-links); returns None if it can't be found."""
    soup = BeautifulSoup(html, "html.parser")
    numbers = []
    for a in soup.select("ul.pagination a.page-link"):
        text = a.get_text(strip=True)
        if text.isdigit():
            numbers.append(int(text))
    return max(numbers) if numbers else None


ALT_REGISTRATION_PREFIX_RE = re.compile(r"^[A-Za-z]{1,4}\s?\d")


def looks_like_registration_number(inner):
    """True if `inner` (the last trailing paren's content) looks like a
    registration number rather than a bare name descriptor like "(MY)" or
    "(Malaysia)".

    Accepts the standard digit-led SSM format, and also sole-proprietorship /
    partnership / Labuan-company formats that use a short letter prefix
    directly against a digit (LLP0003457, JM0564903-X, IP0012550, LL16429,
    P490, ...). Rejects anything containing "/" or "." since those mark
    non-SSM reference numbers (permits, gazette orders, foreign rep-office
    refs, e.g. "PPG/2021/18651", "AKT/14/682/1961", "MIDA.018.600-//37") --
    including ones that would otherwise match the letter-prefix shape, like
    "R28636/06".
    """
    if not inner:
        return False
    if inner[0].isdigit():
        return True
    if "/" in inner or "." in inner:
        return False
    return bool(ALT_REGISTRATION_PREFIX_RE.match(inner))


def extract_registration(raw_name):
    """Split a raw company-name string into (company_name, registration_no).

    The registration number is the LAST balanced top-level parenthetical
    group in the string, but only if its content looks_like_registration_number
    -- that's what distinguishes it from a legitimate parenthetical in the
    company name itself (e.g. "(MY)", "(Malaysia)"). Returns
    (raw_name, None) if no such group is found.
    """
    name = raw_name.strip()
    if not name.endswith(")"):
        return name, None

    depth = 0
    i = len(name) - 1
    end = i
    start = None
    while i >= 0:
        if name[i] == ")":
            depth += 1
        elif name[i] == "(":
            depth -= 1
            if depth == 0:
                start = i
                break
        i -= 1
    if start is None:
        return name, None

    inner = name[start + 1:end].strip()

    # Some rows wrap an otherwise-normal registration number in a redundant
    # extra pair of parens, e.g. "Sdn Bhd ((524706-X))" -- unwrap one more
    # layer if the whole inner content is itself a single parenthesized group.
    if inner.startswith("(") and inner.endswith(")"):
        unwrapped = inner[1:-1].strip()
        if looks_like_registration_number(unwrapped):
            inner = unwrapped

    if not looks_like_registration_number(inner):
        return name, None

    company_name = name[:start].strip()
    return company_name, inner


def parse_page(html):
    """Return a list of row dicts: {raw_name, phone, address, website, raw_html}."""
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for vstack in soup.select("div.vstack"):
        name_span = vstack.select_one("div.company-name span")
        if not name_span:
            continue
        raw_name = name_span.get_text(strip=True)

        phone = address = website = None
        for info in vstack.select("div.contact-section div.contact-info"):
            icon = info.select_one("i")
            icon_classes = icon.get("class", []) if icon else []
            text_span = info.select_one("span.contact-info-text")
            if not text_span:
                continue
            if "bi-telephone-fill" in icon_classes:
                phone = text_span.get_text(strip=True)
            elif "bi-geo-alt" in icon_classes:
                address = text_span.get_text(strip=True)
            elif "bi-globe" in icon_classes:
                link = text_span.select_one("a")
                website = link["href"].strip() if link and link.get("href") else text_span.get_text(strip=True)

        rows.append({
            "raw_name": raw_name,
            "phone": phone,
            "address": address,
            "website": website,
            "raw_html": str(vstack),
        })
    return rows


UPSERT_SQL = """
INSERT INTO staging_fmm (
    registration_no, company_name, phone, address, website,
    source_site, raw_html_path, raw
) VALUES (
    %(registration_no)s, %(company_name)s, %(phone)s, %(address)s, %(website)s,
    %(source_site)s, %(raw_html_path)s, %(raw)s
)
ON CONFLICT (registration_no) DO UPDATE SET
    company_name = EXCLUDED.company_name,
    phone = EXCLUDED.phone,
    address = EXCLUDED.address,
    website = EXCLUDED.website,
    source_site = EXCLUDED.source_site,
    raw_html_path = EXCLUDED.raw_html_path,
    raw = EXCLUDED.raw,
    scraped_at = NOW()
RETURNING (xmax = 0) AS inserted;
"""


def upsert_company(conn, record):
    row = strip_nul_bytes({
        "registration_no": record["registration_no"],
        "company_name": record.get("company_name"),
        "phone": record.get("phone"),
        "address": record.get("address"),
        "website": record.get("website"),
        "source_site": SOURCE_SITE,
        "raw_html_path": record.get("raw_html_path"),
    })
    row["raw"] = psycopg2.extras.Json(strip_nul_bytes(record.get("raw") or {}))
    with conn.cursor() as cur:
        cur.execute(UPSERT_SQL, row)
        inserted = cur.fetchone()[0]
    conn.commit()
    return inserted


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-pages", type=int, default=None,
        help="Only scrape the first N pages (for testing). Default: all pages.",
    )
    return parser.parse_args()


def main():
    load_dotenv()
    args = parse_args()
    database_url = os.environ["DATABASE_URL"]
    os.makedirs(RAW_HTML_DIR, exist_ok=True)

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    conn = psycopg2.connect(database_url)

    stats = {
        "pages_scraped": 0,
        "companies_scraped": 0,
        "inserted": 0,
        "updated": 0,
        "with_website": 0,
        "with_phone": 0,
        "registration_extraction_failed": 0,
    }
    extraction_failures = []
    failed_pages = []

    try:
        log.info("Fetching page 1 to determine total page count...")
        first_html = fetch_page(session, 1)
        total_pages = parse_total_pages(first_html)
        if args.max_pages:
            total_pages = min(args.max_pages, total_pages) if total_pages else args.max_pages
        log.info("Total pages to scrape: %s", total_pages)

        page = 1
        html = first_html
        while True:
            if total_pages and page > total_pages:
                break
            try:
                if page > 1:
                    html = fetch_page(session, page)

                raw_html_path = os.path.join(RAW_HTML_DIR, f"page_{page}.html")
                with open(raw_html_path, "w", encoding="utf-8") as f:
                    f.write(html)

                rows = parse_page(html)
                if not rows:
                    log.info("Page %d returned zero company rows; stopping.", page)
                    break

                log.info("Page %d/%s: %d companies", page, total_pages or "?", len(rows))

                for row in rows:
                    company_name, registration_no = extract_registration(row["raw_name"])
                    if registration_no is None:
                        stats["registration_extraction_failed"] += 1
                        extraction_failures.append({"page": page, "raw_name": row["raw_name"]})
                        log.warning(
                            "Page %d: registration_no extraction FAILED for raw name %r",
                            page, row["raw_name"],
                        )
                        continue

                    record = {
                        "registration_no": registration_no,
                        "company_name": company_name,
                        "phone": row["phone"],
                        "address": row["address"],
                        "website": row["website"],
                        "raw_html_path": raw_html_path,
                        "raw": {"raw_name": row["raw_name"], "raw_html": row["raw_html"], "page": page},
                    }
                    inserted = upsert_company(conn, record)
                    stats["companies_scraped"] += 1
                    stats["inserted" if inserted else "updated"] += 1
                    if record["website"]:
                        stats["with_website"] += 1
                    if record["phone"]:
                        stats["with_phone"] += 1

                stats["pages_scraped"] += 1

            except Exception as exc:
                failed_pages.append({"page": page, "error": str(exc)})
                log.error("Failed on page %d: %s", page, exc)

            page += 1
            sleep_politely()

    finally:
        conn.close()

    summary = {
        "total_pages_detected": total_pages,
        **stats,
        "extraction_failures": extraction_failures,
        "failed_pages": failed_pages,
    }
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n=== FMM Malaysia scrape summary ===")
    print(f"Total pages detected:              {total_pages}")
    print(f"Pages scraped:                      {stats['pages_scraped']}")
    print(f"Companies scraped:                  {stats['companies_scraped']}")
    print(f"  New rows inserted:                {stats['inserted']}")
    print(f"  Existing rows updated:             {stats['updated']}")
    print(f"With website:                       {stats['with_website']}")
    print(f"With phone:                          {stats['with_phone']}")
    print(f"registration_no extraction failed:  {stats['registration_extraction_failed']}")
    if extraction_failures:
        print("  Failed rows:")
        for f in extraction_failures:
            print(f"    page {f['page']}: {f['raw_name']!r}")
    if failed_pages:
        print(f"Failed pages: {len(failed_pages)}")
        for fp in failed_pages:
            print(f"    page {fp['page']}: {fp['error']}")


if __name__ == "__main__":
    main()
