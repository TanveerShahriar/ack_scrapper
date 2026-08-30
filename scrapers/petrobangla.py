"""Petrobangla tender crawler for the public tender listings page."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import requests
from bs4 import BeautifulSoup

requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]

TENDER_URL = "https://petrobangla.org.bd/pages/tenders?page=1&page_size=100"
DATA_PATH = "data/petrobangla/tender.json"


def fetch_html(url: str = TENDER_URL, timeout: int = 30) -> str:
    """Fetch the Petrobangla tender page HTML."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    response = requests.get(url, headers=headers, timeout=timeout, verify=False)
    response.raise_for_status()
    return response.text


def clean_text(value: Any) -> str:
    """Convert a BeautifulSoup node or any value into clean text."""
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    else:
        text = value.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_table_rows(html: str) -> list[dict[str, Any]]:
    """Extract all actual data rows with class 'table-tr' from the page."""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, Any]] = []

    for tr in soup.select("tr.table-tr"):
        if tr.select("th") and not tr.select("td"):
            continue

        td_cells = tr.select("td")
        if not td_cells:
            continue

        row: dict[str, Any] = {"raw_html": str(tr)}
        for td in td_cells:
            column_name = td.get("data-column")
            if not column_name:
                continue

            if column_name == "files":
                file_links = [link.get("href") for link in td.select("a[href]") if link.get("href")]
                row["files"] = file_links
                row["pdf_url"] = file_links[0] if file_links else ""
            elif column_name == "publish_date":
                value = clean_text(td)
                row["publish_date"] = value
                row["published_date"] = value
            else:
                row[column_name] = clean_text(td)

        if row and len(row) > 1:
            rows.append(row)

    return rows


def _tender_key(tender: dict[str, Any]) -> str:
    """Build a stable identifier for comparing tender rows."""
    title = str(tender.get("title") or "").strip().lower()
    publish_date = str(tender.get("published_date") or tender.get("publish_date") or "").strip().lower()
    tender_no = str(tender.get("tender_no") or "").strip().lower()
    pdf_url = str(tender.get("pdf_url") or "").strip().lower()
    return "|".join(part for part in [title, publish_date, tender_no, pdf_url] if part)


def load_saved_tenders(path: str = DATA_PATH) -> list[dict[str, Any]]:
    """Load previously saved Petrobangla tenders from disk."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as file_handle:
            data = json.load(file_handle)
    except (OSError, json.JSONDecodeError):
        return []

    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict) and isinstance(data.get("tenders"), list):
        return [item for item in data["tenders"] if isinstance(item, dict)]
    return []


def save_tenders(tenders: list[dict[str, Any]], path: str = DATA_PATH) -> None:
    """Persist the latest Petrobangla tenders to disk."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(path, "w", encoding="utf-8") as file_handle:
        json.dump(tenders, file_handle, ensure_ascii=False, indent=2)


def print_rows(rows: list[dict[str, Any]]) -> None:
    """Print the scraped results in a readable console format."""
    print(f"Total table-tr rows found: {len(rows)}\n")
    for index, row in enumerate(rows, start=1):
        print(f"Row {index}:")
        for key, value in row.items():
            if key == "raw_html":
                continue
            print(f"  {key}: {value}")
        print("-" * 80)


def sync_tenders(path: str = DATA_PATH, send_notifications: bool = True) -> dict[str, Any]:
    """Fetch the latest Petrobangla tenders, compare with saved data, and notify on new rows."""
    html = fetch_html()
    latest_tenders = extract_table_rows(html)
    saved_tenders = load_saved_tenders(path)
    saved_keys = {_tender_key(item) for item in saved_tenders}
    new_tenders = [tender for tender in latest_tenders if _tender_key(tender) not in saved_keys]

    if new_tenders or not saved_tenders:
        save_tenders(latest_tenders, path)

    if send_notifications and new_tenders:
        try:
            from notifications.email import send_bbtender_notifications

            sent = send_bbtender_notifications(new_tenders)
            if sent:
                print(f"Email sent for {len(new_tenders)} new Petrobangla tender(s).")
            else:
                print("No Petrobangla email sent because no recipients were configured.")
        except Exception:
            print("Petrobangla email notification failed; continuing with saved data.")

        try:
            from notifications.telegram import send_bbtender_notifications as send_telegram_notifications

            sent = send_telegram_notifications(new_tenders)
            if sent:
                print(f"Telegram sent for {len(new_tenders)} new Petrobangla tender(s).")
            else:
                print("No Petrobangla Telegram sent because no bot token/chat IDs were configured.")
        except Exception:
            print("Petrobangla Telegram notification failed; continuing with saved data.")

    print(f"Petrobangla tenders fetched: {len(latest_tenders)}")
    print(f"New Petrobangla tenders: {len(new_tenders)}")
    return {
        "updated": bool(new_tenders or not saved_tenders),
        "saved_path": path,
        "total_loaded": len(latest_tenders),
        "new_count": len(new_tenders),
        "new_tenders": new_tenders,
    }


def run() -> dict[str, Any]:
    """Run the Petrobangla scraper with default storage and notifications."""
    return sync_tenders(path=DATA_PATH, send_notifications=True)


def main() -> None:
    """Fetch the URL, compare against saved data, and print the tender rows in the console."""
    html = fetch_html()
    rows = extract_table_rows(html)
    print_rows(rows)
    sync_tenders(path=DATA_PATH, send_notifications=True)


if __name__ == "__main__":
    main()
