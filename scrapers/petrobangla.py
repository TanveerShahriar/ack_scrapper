"""Petrobangla tender crawler for the public tender listings page."""

from __future__ import annotations

import re
from typing import Any

import requests
from bs4 import BeautifulSoup

requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]

TENDER_URL = "https://petrobangla.org.bd/pages/tenders?page=1&page_size=100"


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
                row[column_name] = file_links if file_links else clean_text(td)
            else:
                row[column_name] = clean_text(td)

        if row and len(row) > 1:
            rows.append(row)

    return rows


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


def main() -> None:
    """Fetch the URL and print the tender rows in the console."""
    html = fetch_html()
    rows = extract_table_rows(html)
    print_rows(rows)


if __name__ == "__main__":
    main()
