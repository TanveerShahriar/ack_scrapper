"""Email notifier for tender updates.

Usage: call `send_update_notifications(summary)` where `summary` is the dict
returned by `scrapers.tenderbazar.collect_all_tenders()`.

Configuration via environment variables (optional):
- SMTP_HOST (default: localhost)
- SMTP_PORT (default: 25)
- SMTP_USER
- SMTP_PASS
- SMTP_FROM (default: no-reply@localhost)

If SMTP_USER/SMTP_PASS are not set, the module will attempt to send without auth.
"""
from __future__ import annotations

import json
import os
import smtplib
from email.message import EmailMessage
from typing import List


def _load_recipients(path: str = "data/user.json") -> List[str]:
    candidates = [path]
    # also try relative to project root (two dirs up from this file)
    project_relative = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "user.json")
    candidates.append(project_relative)
    # also try cwd + path
    candidates.append(os.path.join(os.getcwd(), path))

    for p in candidates:
        try:
            if not os.path.exists(p):
                continue
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            recs = [e for e in data.get("emails", []) if isinstance(e, str)]
            if recs:
                return recs
        except Exception:
            continue
    # nothing found
    return []


def _smtp_config_from_env():
    # prefer real environment variables, but fall back to a .env file in the project root
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
                # stop at the first dotenv we find
                return out
            except Exception:
                continue
        return out

    dotenv = _load_dotenv()
    # use env vars when present, otherwise use .env values
    def get(k: str, default: str | None = None) -> str | None:
        return env.get(k) or dotenv.get(k) or default

    port_val = get("SMTP_PORT", "25")
    try:
        port_int = int(port_val)
    except Exception:
        port_int = 25

    return {
        "host": get("SMTP_HOST", "localhost"),
        "port": port_int,
        "user": get("SMTP_USER"),
        "pass": get("SMTP_PASS"),
        "from": get("SMTP_FROM", "no-reply@localhost"),
    }


def _build_message(from_addr: str, to_addrs: List[str], subject: str, body: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_addrs)
    msg["Subject"] = subject
    msg.set_content(body)
    return msg


def send_update_notifications(summary: dict, recipients: List[str] | None = None) -> bool:
    """Send email to recipients if there are updates.

    summary: dict returned by `collect_all_tenders`.
    Returns True if emails were sent (or at least attempted), False otherwise.
    """
    if not summary or summary.get("total_new_tender_ids", 0) == 0:
        return False

    if recipients is None:
        recipients = _load_recipients()
    if not recipients:
        return False

    cfg = _smtp_config_from_env()
    subject = f"TenderBazar updates: {summary['total_new_tender_ids']} new tenders"
    # Build a short body listing changed products and their new IDs
    lines = [
        f"Total products checked: {summary.get('total_products_checked')}",
        f"Products with new tenders: {summary.get('products_with_new_tenders')}",
        f"Total new tender IDs added: {summary.get('total_new_tender_ids')}",
        "",
        "Details:",
    ]
    for ent in summary.get("changed_entries", []):
        lines.append(f"- {ent.get('name')} (pro={ent.get('pro')}): {', '.join(ent.get('new_ids', []))}")

    body = "\n".join(lines)

    msg = _build_message(cfg["from"], recipients, subject, body)

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"]) as s:
            s.ehlo()
            if cfg.get("user") and cfg.get("pass"):
                s.starttls()
                s.login(cfg["user"], cfg["pass"])
            s.send_message(msg)
        return True
    except Exception:
        # print debug to console for easier troubleshooting
        import traceback
        traceback.print_exc()
        return False


def send_bbtender_notifications(tenders: List[dict], recipients: List[str] | None = None) -> bool:
    """Send email for newly added Bangladesh Bank tenders with their PDF links."""
    if not tenders:
        return False

    if recipients is None:
        recipients = _load_recipients()
    if not recipients:
        return False

    cfg = _smtp_config_from_env()
    subject = f"Bangladesh Bank tender update: {len(tenders)} new tender(s)"

    lines = [
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
    msg = _build_message(cfg["from"], recipients, subject, body)

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"]) as s:
            s.ehlo()
            if cfg.get("user") and cfg.get("pass"):
                s.starttls()
                s.login(cfg["user"], cfg["pass"])
            s.send_message(msg)
        return True
    except Exception:
        import traceback
        traceback.print_exc()
        return False
