"""Meghna Petrolium tender crawler configuration."""

from __future__ import annotations
import os
import sys
from typing import Any

if __package__:
    from .tender_site import clean_text, extract_table_rows, print_rows
    from .tender_site import fetch_html as _fetch_html
    from .tender_site import load_saved_tenders as _load_saved_tenders
    from .tender_site import save_tenders as _save_tenders
    from .tender_site import sync_tenders as _sync_tenders
    from .tender_site import tender_key
else:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from tender_site import clean_text, extract_table_rows, print_rows
    from tender_site import fetch_html as _fetch_html
    from tender_site import load_saved_tenders as _load_saved_tenders
    from tender_site import save_tenders as _save_tenders
    from tender_site import sync_tenders as _sync_tenders
    from tender_site import tender_key

TENDER_URL = "https://mpl.gov.bd/pages/tenders?page=1&page_size=100&search=audit"
DATA_PATH = "data/meghna_petrolium/tender.json"

def fetch_html(url: str = TENDER_URL, timeout: int = 30) -> str:
    return _fetch_html(url, timeout)

def _tender_key(tender: dict[str, Any]) -> str:
    return tender_key(tender)

def load_saved_tenders(path: str = DATA_PATH) -> list[dict[str, Any]]:
    return _load_saved_tenders(path)

def save_tenders(tenders: list[dict[str, Any]], path: str = DATA_PATH) -> None:
    _save_tenders(tenders, path)

def sync_tenders(path: str = DATA_PATH, send_notifications: bool = True) -> dict[str, Any]:
    return _sync_tenders("Meghna Petrolium", TENDER_URL, path, send_notifications)

def run() -> dict[str, Any]:
    return sync_tenders(path=DATA_PATH, send_notifications=True)

def main() -> None:
    html = fetch_html()
    print_rows(extract_table_rows(html))
    sync_tenders(path=DATA_PATH, send_notifications=True)
    
if __name__ == "__main__":
    main()
