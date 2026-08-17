"""Telegram notifier for tender updates.

Usage: call `send_update_notifications(summary)` where `summary` is the dict
returned by `scrapers.tenderbazar.collect_all_tenders()`.

Configuration via environment variables (recommended):
- TELEGRAM_BOT_TOKEN (required)
- TELEGRAM_CHAT_IDS (optional, comma-separated)

Chat IDs can also be loaded from `data/user.json` under:
- telegram_chat_ids: ["123456789", "-100987654321"]
- telegram_chat_id: "123456789"
"""
from __future__ import annotations

import json
import os
from typing import List

import requests


def _load_chat_ids(path: str = "data/user.json") -> List[str]:
    candidates = [path]
    project_relative = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "user.json"
    )
    candidates.append(project_relative)
    candidates.append(os.path.join(os.getcwd(), path))

    for p in candidates:
        try:
            if not os.path.exists(p):
                continue
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)

            values: list[str] = []
            ids = data.get("telegram_chat_ids", [])
            if isinstance(ids, list):
                for item in ids:
                    if isinstance(item, (str, int)):
                        values.append(str(item).strip())

            single = data.get("telegram_chat_id")
            if isinstance(single, (str, int)):
                values.append(str(single).strip())

            # de-duplicate while preserving order
            unique = list(dict.fromkeys([v for v in values if v]))
            if unique:
                return unique
        except Exception:
            continue

    return []


def _telegram_config_from_env() -> dict:
    env = dict(os.environ)

    def _load_dotenv(path: str = ".env") -> dict:
        candidates = [path]
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidates.append(os.path.join(project_root, path))
        candidates.append(os.path.join(os.getcwd(), path))

        out: dict = {}
        for p in candidates:
            try:
                if not os.path.exists(p):
                    continue
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        out[k] = v
                return out
            except Exception:
                continue
        return out

    dotenv = _load_dotenv()

    def get(k: str, default: str | None = None) -> str | None:
        return env.get(k) or dotenv.get(k) or default

    chat_ids_raw = get("TELEGRAM_CHAT_IDS", "") or ""
    chat_ids = [chunk.strip() for chunk in chat_ids_raw.split(",") if chunk.strip()]

    return {
        "token": get("TELEGRAM_BOT_TOKEN"),
        "chat_ids": chat_ids,
    }


def _send_text(token: str, chat_id: str, text: str, timeout: int = 20) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        if resp.status_code >= 400:
            print(f"Telegram send failed for chat_id={chat_id}: {resp.status_code} {resp.text}")
            return False
        body = resp.json()
        if not body.get("ok"):
            print(f"Telegram API returned non-ok for chat_id={chat_id}: {body}")
            return False
        return True
    except Exception:
        import traceback

        traceback.print_exc()
        return False


def _send_multiline_message(token: str, chat_id: str, text: str) -> bool:
    # Telegram hard limit is 4096 characters per message.
    max_len = 3900
    if len(text) <= max_len:
        return _send_text(token, chat_id, text)

    lines = text.splitlines()
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in lines:
        add_len = len(line) + 1
        if current and current_len + add_len > max_len:
            chunks.append("\n".join(current))
            current = [line]
            current_len = add_len
        else:
            current.append(line)
            current_len += add_len

    if current:
        chunks.append("\n".join(current))

    ok = True
    for chunk in chunks:
        if not _send_text(token, chat_id, chunk):
            ok = False
            break
    return ok


def send_update_notifications(summary: dict, chat_ids: List[str] | None = None) -> bool:
    """Send Telegram updates for TenderBazar summary if there are new tenders."""
    if not summary or summary.get("total_new_tender_ids", 0) == 0:
        return False

    cfg = _telegram_config_from_env()
    token = cfg.get("token")
    if not token:
        return False

    if chat_ids is None:
        chat_ids = cfg.get("chat_ids") or _load_chat_ids()
    if not chat_ids:
        return False

    lines = [
        f"TenderBazar updates: {summary.get('total_new_tender_ids', 0)} new tenders",
        "",
        f"Total products checked: {summary.get('total_products_checked')}",
        f"Products with new tenders: {summary.get('products_with_new_tenders')}",
        f"Total new tender IDs added: {summary.get('total_new_tender_ids')}",
        "",
        "Details:",
    ]
    for ent in summary.get("changed_entries", []):
        lines.append(
            f"- {ent.get('name')} (pro={ent.get('pro')}): {', '.join(ent.get('new_ids', []))}"
        )

    body = "\n".join(lines)

    any_sent = False
    for chat_id in chat_ids:
        sent = _send_multiline_message(token, chat_id, body)
        any_sent = any_sent or sent
    return any_sent


def send_bbtender_notifications(tenders: List[dict], chat_ids: List[str] | None = None) -> bool:
    """Send Telegram updates for newly added Bangladesh Bank tenders."""
    if not tenders:
        return False

    cfg = _telegram_config_from_env()
    token = cfg.get("token")
    if not token:
        return False

    if chat_ids is None:
        chat_ids = cfg.get("chat_ids") or _load_chat_ids()
    if not chat_ids:
        return False

    lines = [
        f"Bangladesh Bank tender update: {len(tenders)} new tender(s)",
        "",
        "New Bangladesh Bank tender(s) detected:",
        "",
    ]

    for tender in tenders:
        title = tender.get("title") or "Untitled tender"
        published = tender.get("published_date") or "-"
        closing = tender.get("closing_date") or "-"
        pdf_url = tender.get("pdf_url") or "-"
        lines.append(f"- {title}")
        lines.append(f"  Published: {published}")
        lines.append(f"  Closing: {closing}")
        lines.append(f"  PDF: {pdf_url}")
        lines.append("")

    body = "\n".join(lines)

    any_sent = False
    for chat_id in chat_ids:
        sent = _send_multiline_message(token, chat_id, body)
        any_sent = any_sent or sent
    return any_sent