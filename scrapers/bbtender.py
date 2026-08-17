"""Bangladesh Bank tender fetcher: hit the tenders page, compare with saved data, and notify on new rows."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.bb.org.bd"
TENDER_URL = "https://www.bb.org.bd/en/index.php/about/tenders"


def fetch_html(url: str = TENDER_URL, timeout: int = 20) -> str:
    """Fetch the Bangladesh Bank tender page."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Scraper/1.0; +https://example.com)"
    }
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.text


def _clean_text(node: Any) -> str:
    if node is None:
        return ""
    text = node.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_table_rows(soup: BeautifulSoup) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for tr in soup.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 4:
            continue
        serial = _clean_text(cells[0])
        published_date = _clean_text(cells[1])
        closing_date = _clean_text(cells[2])
        title_cell = cells[3]
        title = _clean_text(title_cell)
        title = re.sub(r"\s*details\.\.\.\s*$", "", title, flags=re.IGNORECASE)
        title = title.strip()
        if not serial or not published_date or not closing_date or not title:
            continue
        pdf_url = ""
        pdf_link = title_cell.select_one("a.pdf-file")
        if pdf_link:
            pdf_url = pdf_link.get("pdf-link") or pdf_link.get("href") or ""
        rows.append(
            {
                "serial": serial,
                "published_date": published_date,
                "closing_date": closing_date,
                "title": title,
                "pdf_url": pdf_url,
            }
        )
    return rows


def _extract_fallback_rows(html: str) -> list[dict[str, str]]:
    """Fallback parser for pages that render rows as plain text rather than td cells."""
    cleaned = re.sub(r"\s+", " ", html)
    pattern = re.compile(
        r"(?P<serial>\d+)\s*(?P<published>\d{2}-\d{2}-\d{4})\s*(?P<closing>\d{2}-\d{2}-\d{4})\s*(?P<title>.*?)(?=(?:\s+\d+\s+\d{2}-\d{2}-\d{4}\s+\d{2}-\d{2}-\d{4})|(?:\s+Showing\s+\d+\s+to\s+\d+\s+of\s+\d+\s+entries)|$)",
        re.DOTALL | re.IGNORECASE,
    )
    rows: list[dict[str, str]] = []
    for match in pattern.finditer(cleaned):
        serial = match.group("serial").strip()
        published = match.group("published").strip()
        closing = match.group("closing").strip()
        title = re.sub(r"\s+", " ", match.group("title")).strip()
        title = re.sub(r"\s*details\.\.\.\s*$", "", title, flags=re.IGNORECASE)
        if not title:
            continue
        rows.append(
            {
                "serial": serial,
                "published_date": published,
                "closing_date": closing,
                "title": title,
                "pdf_url": "",
            }
        )
    return rows


def extract_tenders(html: str) -> list[dict[str, str]]:
    """Extract tender rows from the Bangladesh Bank page."""
    soup = BeautifulSoup(html, "html.parser")
    rows = _extract_table_rows(soup)
    if rows:
        return rows
    return _extract_fallback_rows(html)


def _tender_key(tender: dict[str, str]) -> str:
    pdf_url = (tender.get("pdf_url") or "").strip()
    if pdf_url:
        return pdf_url.lower()
    key = (
        f"{tender.get('serial', '')}|{tender.get('published_date', '')}|"
        f"{tender.get('closing_date', '')}|{tender.get('title', '')}"
    )
    return key.strip().lower()


def load_saved_tenders(path: str = "data/bbtender/tender.json") -> list[dict[str, str]]:
    """Load previously stored Bangladesh Bank tenders from disk."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return []

    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict) and isinstance(data.get("tenders"), list):
        return [item for item in data["tenders"] if isinstance(item, dict)]
    return []


def save_tenders(tenders: list[dict[str, str]], path: str = "data/bbtender/tender.json") -> None:
    """Persist the current Bangladesh Bank tender list to disk."""
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(tenders, fh, ensure_ascii=False, indent=2)


def sync_tenders(path: str = "data/bbtender/tender.json", send_email: bool = True) -> dict[str, Any]:
    """Fetch latest tenders, compare against saved file, update if new, and email the additions."""
    html = fetch_html()
    latest_tenders = extract_tenders(html)
    saved_tenders = load_saved_tenders(path)
    saved_keys = {_tender_key(item) for item in saved_tenders}
    new_tenders = [item for item in latest_tenders if _tender_key(item) not in saved_keys]

    updated = False
    if not saved_tenders or new_tenders:
        save_tenders(latest_tenders, path)
        updated = True

    if send_email and new_tenders:
        try:
            from notifications.email import send_bbtender_notifications

            sent = send_bbtender_notifications(new_tenders)
            if sent:
                print(f"Email sent for {len(new_tenders)} new Bangladesh Bank tender(s).")
            else:
                print("No Bangladesh Bank email sent because no recipients were configured.")
        except Exception:
            print("Bangladesh Bank email notification failed; continuing with saved data.")

        try:
            from notifications.telegram import send_bbtender_notifications as send_bbtender_telegram_notifications

            sent = send_bbtender_telegram_notifications(new_tenders)
            if sent:
                print(f"Telegram sent for {len(new_tenders)} new Bangladesh Bank tender(s).")
            else:
                print("No Bangladesh Bank Telegram sent because no bot token/chat IDs were configured.")
        except Exception:
            print("Bangladesh Bank Telegram notification failed; continuing with saved data.")

    print(f"Saved tenders: {len(latest_tenders)} total")
    if new_tenders:
        print(f"New Bangladesh Bank tender(s): {len(new_tenders)}")
    else:
        print("No new Bangladesh Bank tender(s) found.")

    return {
        "updated": updated,
        "saved_path": path,
        "total_loaded": len(latest_tenders),
        "new_count": len(new_tenders),
        "new_tenders": new_tenders,
    }


def print_tenders() -> list[dict[str, str]]:
    """Fetch the page, extract tenders, and print them to the console."""
    html = fetch_html()
    tenders = extract_tenders(html)

    if not tenders:
        print("No tender rows found on the page.")
        return tenders

    print(f"Found {len(tenders)} tenders on {TENDER_URL}\n")
    for item in tenders:
        print(f"{item['serial']}. {item['title']}")
        print(f"  Published: {item['published_date']}")
        print(f"  Closing:   {item['closing_date']}")
        if item.get("pdf_url"):
            print(f"  PDF:       {item['pdf_url']}")
        print()

    return tenders


def main() -> None:
    sync_tenders()


if __name__ == "__main__":
    main()
