"""eProcure tender scraper with persistent storage and notifications."""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import requests
from bs4 import BeautifulSoup

URL = "https://www.eprocure.gov.bd/TenderDetailsServlet"
DATA_PATH = "data/eprocure/tender.json"
KEYWORDS = ["audit ", "auditor ", "accountant ", "auditing "]
PAGE_SIZE = 200

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def extract_tenders(session: requests.Session | None = None) -> list[dict[str, str | None]]:
    """Fetch and extract eProcure tenders for all configured keywords."""
    client = session or requests.Session()
    all_rows = []

    for keyword in KEYWORDS:
        page = 1
        while True:
            payload = {
                "funName": "AllTenders",
                "keyword": keyword,
                "pageNo": str(page),
                "size": str(PAGE_SIZE),
                "homeWSearch": "homeWSearch",
                "approve": "false",
                "h": "t",
            }
            response = client.post(URL, data=payload, timeout=30)
            response.raise_for_status()
            rows = BeautifulSoup(response.text, "html.parser").find_all("tr")
            all_rows.extend(rows)
            page += 1
            if len(rows) < PAGE_SIZE:
                break

    unique_rows = []
    seen_rows = set()
    for row in all_rows:
        row_key = tuple(row)
        if row_key not in seen_rows:
            seen_rows.add(row_key)
            unique_rows.append(row)

    extracted_tenders: list[dict[str, str | None]] = []
    for row in unique_rows:
        cells = row.find_all("td")
        if len(cells) < 6:
            continue

        tender_type = cells[2].get_text(" ", strip=True).split(",")[0]
        brief_span = cells[2].find(
            "span", id=lambda value: value and value.startswith("tenderBrief_")
        )
        tender_brief = brief_span.get_text(" ", strip=True) if brief_span else ""
        date_text = list(cells[5].stripped_strings)
        id_input = cells[2].find("input", {"name": "id"})
        tender_id = id_input.get("value") if id_input else None
        link = (
            f"https://www.eprocure.gov.bd/resources/common/ViewTender.jsp?id={tender_id}&h=t"
            if tender_id
            else None
        )
        extracted_tenders.append(
            {
                "name": f"{tender_type}, {tender_brief}",
                "publish_date": date_text[0] if date_text else None,
                "closing_date": date_text[1] if len(date_text) > 1 else None,
                "link": link,
            }
        )

    return extracted_tenders


def _tender_key(tender: dict[str, Any]) -> str:
    link = str(tender.get("link") or "").strip().lower()
    if link:
        return link
    return "|".join(
        str(tender.get(field) or "").strip().lower()
        for field in ("name", "publish_date", "closing_date")
    )


def load_saved_tenders(path: str = DATA_PATH) -> list[dict[str, Any]]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as file_handle:
            data = json.load(file_handle)
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def save_tenders(tenders: list[dict[str, Any]], path: str = DATA_PATH) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file_handle:
        json.dump(tenders, file_handle, ensure_ascii=False, indent=2)


def sync_tenders(path: str = DATA_PATH, send_notifications: bool = True) -> dict[str, Any]:
    extracted_tenders = extract_tenders()
    saved_tenders = load_saved_tenders(path)
    saved_keys = {_tender_key(tender) for tender in saved_tenders}
    new_tenders = []
    for tender in extracted_tenders:
        tender_key = _tender_key(tender)
        if tender_key not in saved_keys:
            new_tenders.append(tender)
            saved_keys.add(tender_key)

    if new_tenders:
        save_tenders(saved_tenders + new_tenders, path)

    if send_notifications and new_tenders:
        notification_tenders = [
            {
                "title": tender.get("name"),
                "published_date": tender.get("publish_date"),
                "closing_date": tender.get("closing_date"),
                "pdf_url": tender.get("link"),
            }
            for tender in new_tenders
        ]
        try:
            from notifications.email import send_bbtender_notifications

            send_bbtender_notifications(notification_tenders)
        except Exception as error:
            print(f"eProcure email notification failed: {error}")
        try:
            from notifications.telegram import send_bbtender_notifications

            send_bbtender_notifications(notification_tenders)
        except Exception as error:
            print(f"eProcure Telegram notification failed: {error}")

    print(f"eProcure tenders fetched: {len(extracted_tenders)}")
    print(f"New eProcure tenders: {len(new_tenders)}")
    return {
        "updated": bool(new_tenders),
        "saved_path": path,
        "total_loaded": len(extracted_tenders),
        "new_count": len(new_tenders),
        "new_tenders": new_tenders,
    }


def run() -> dict[str, Any]:
    """Run the eProcure scraper with default storage and notifications."""
    return sync_tenders(path=DATA_PATH, send_notifications=True)


if __name__ == "__main__":
    run()
