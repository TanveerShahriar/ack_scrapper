"""Collect BDTender financial service tenders and notify on new records."""

from __future__ import annotations
import json
import os
import re
from typing import Any

from bs4 import BeautifulSoup, Tag
from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

TENDER_URL = (
    "https://bdtender.com/ind/Cat-197/business-services/financial-Insurance-services/"
    "audit-audit-financial-services-tender-notice"
)
PAGE_URL = "https://bdtender.com/tender-category-search-ajax?page={page}&cat=Cat-197"
DATA_PATH = "data/bdtender_financial_service/tender.json"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

def _load_page(page: Page, url: str, selector: str, timeout: int) -> str:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
        page.wait_for_selector(selector, timeout=timeout * 1000)
    except PlaywrightTimeoutError as error:
        raise RuntimeError(f"Timed out waiting for {selector} at {url}") from error
    return page.content()


def fetch_html(url: str = TENDER_URL, timeout: int = 20) -> str:
    """Fetch the rendered financial services page."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT)
        try:
            return _load_page(context.new_page(), url, "ul.pagination", timeout)
        finally:
            browser.close()


def get_second_last_pagination_item(html: str) -> Tag:
    """Return the second-last list item in the pagination list."""
    soup = BeautifulSoup(html, "html.parser")
    pagination = soup.select_one("ul.pagination")
    if pagination is None:
        raise ValueError("Could not find ul.pagination on the page")

    items = pagination.find_all("li", recursive=False)
    if len(items) < 2:
        raise ValueError("Pagination contains fewer than two list items")
    return items[-2]

def get_max_page_number(html: str) -> int:
    """Read the maximum page number from the second-last pagination item."""
    item_text = get_second_last_pagination_item(html).get_text(" ", strip=True)
    match = re.search(r"\d+", item_text)
    if match is None:
        raise ValueError(f"Could not read a page number from pagination item: {item_text!r}")
    return int(match.group())


def _extract_value(text: str, label: str, next_label: str) -> str:
    match = re.search(
    rf"{re.escape(label)}\s*(.*?)(?=\s+{re.escape(next_label)}|$)",
    text,
    flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""


def extract_tenders(html: str) -> list[dict[str, str]]:
    """Extract tender records from one rendered AJAX response."""
    soup = BeautifulSoup(html, "html.parser")
    tenders: list[dict[str, str]] = []
    for row in soup.select("div[row][count]"):
        tender_id = str(row.get("row", "")).strip()
        title_link = row.select_one("a.workdescription")
        title = title_link.get_text(" ", strip=True) if title_link else ""
        tender_url = title_link.get("href", "") if title_link else ""
        row_text = re.sub(r"\s+", " ", row.get_text(" ", strip=True))
        if not tender_id or not title:
            continue
        tenders.append(
            {
                "tender_id": tender_id,
                "title": title,
                "published_date": _extract_value(row_text, "Published on:", "Sector:"),
                "sector": _extract_value(row_text, "Sector:", "Earnest Money:"),
                "closing_date": _extract_value(row_text, "Sub. Date:", "Opening Date:"),
                "opening_date": _extract_value(row_text, "Opening Date:", "Visitor :"),
                "pdf_url": tender_url,
            }
        )
    return tenders


def _tender_key(tender: dict[str, str]) -> str:
    return (tender.get("tender_id") or tender.get("pdf_url") or tender.get("title", "")).strip().lower()

def load_saved_tenders(path: str = DATA_PATH) -> list[dict[str, str]]:
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


def save_tenders(tenders: list[dict[str, str]], path: str = DATA_PATH) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file_handle:
        json.dump(tenders, file_handle, ensure_ascii=False, indent=2)


def collect_tenders(timeout: int = 30) -> list[dict[str, str]]:
    """Fetch every financial-service page from 1 through the maximum page."""
    tenders: list[dict[str, str]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()
        try:
            landing_html = _load_page(page, TENDER_URL, "ul.pagination", timeout)
            maximum_page = get_max_page_number(landing_html)
            for page_number in range(1, maximum_page + 1):
                html = _load_page(
                    page,
                    PAGE_URL.format(page=page_number),
                    "div[row][count]",
                    timeout,
                )
                tenders.extend(extract_tenders(html))
        finally:
            browser.close()
    unique_tenders = list({_tender_key(tender): tender for tender in tenders}.values())
    if not unique_tenders:
        raise RuntimeError("BDTender returned no financial service tender rows")
    return unique_tenders


def sync_tenders(path: str = DATA_PATH, send_notifications: bool = True) -> dict[str, Any]:
    latest_tenders = collect_tenders()
    saved_tenders = load_saved_tenders(path)
    saved_keys = {_tender_key(tender) for tender in saved_tenders}
    new_tenders = [tender for tender in latest_tenders if _tender_key(tender) not in saved_keys]

    if new_tenders or not saved_tenders:
        save_tenders(latest_tenders, path)

    if send_notifications and new_tenders:
        try:
            from notifications.email import send_bbtender_notifications

            send_bbtender_notifications(new_tenders)
        except Exception as error:
            print(f"Financial service email notification failed: {error}")
        try:
            from notifications.telegram import send_bbtender_notifications

            send_bbtender_notifications(new_tenders)
        except Exception as error:
            print(f"Financial service Telegram notification failed: {error}")

    print(f"Financial service tenders fetched: {len(latest_tenders)}")
    print(f"New financial service tenders: {len(new_tenders)}")
    return {
        "updated": bool(new_tenders or not saved_tenders),
        "saved_path": path,
        "total_loaded": len(latest_tenders),
        "new_count": len(new_tenders),
        "new_tenders": new_tenders,
    }


def run() -> dict[str, Any]:
    """Run the financial-service scraper with its default storage and notifications."""
    return sync_tenders(
        path=DATA_PATH,
        send_notifications=True,
    )


def main() -> None:
    run()


if __name__ == "__main__":
    main()
