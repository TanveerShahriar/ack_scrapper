"""TenderBazar fetcher: hit the products URL and print the result.

Provides a simple, robust fetcher with retries and optional file output.
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import re


BASE_URL = "https://www.tenderbazar.com"
START_URL = "https://www.tenderbazar.com/Home/Products"


def _session_with_retries(total: int = 3, backoff: float = 0.3) -> requests.Session:
	s = requests.Session()
	retries = Retry(total=total, backoff_factor=backoff, status_forcelist=(500, 502, 503, 504))
	adapter = HTTPAdapter(max_retries=retries)
	s.mount("http://", adapter)
	s.mount("https://", adapter)
	return s


def fetch(url: str, timeout: int = 15) -> Tuple[str, requests.Response]:
	"""Fetch URL and return (text, response).

	Raises on non-success status.
	"""
	headers = {
		"User-Agent": "Mozilla/5.0 (compatible; Scraper/1.0; +https://example.com)"
	}
	s = _session_with_retries()
	resp = s.get(url, headers=headers, timeout=timeout)
	resp.raise_for_status()
	return resp.text, resp


def _is_probably_json(text: str, resp: requests.Response) -> bool:
	ct = resp.headers.get("Content-Type", "")
	if "application/json" in ct:
		return True
	t = text.lstrip()
	return t.startswith("{") or t.startswith("[")


def scrape_structured(out: str | None = None, raw: bool = False, timeout: int = 15) -> str:
	"""Fetch the products page and print the response.

	- If the response is JSON (Content-Type or starts with { or [), pretty-print JSON.
	- Otherwise print raw text.
	- If `out` is provided, the raw response bytes are written to that file.

	Returns the response text.
	"""
	text, resp = fetch(START_URL, timeout=timeout)

	if out:
		with open(out, "wb") as f:
			f.write(resp.content)

	if not raw and _is_probably_json(text, resp):
		try:
			obj = json.loads(text)
			pretty = json.dumps(obj, ensure_ascii=False, indent=2)
			print(pretty)
			return pretty
		except Exception:
			pass

	print(text)
	return text


def _extract_enclosing_json(text: str, pos: int):
	"""Return JSON substring that encloses position pos (starting at an opening [ or {)."""
	# find nearest opening bracket before pos
	start = None
	open_ch = None
	for i in range(pos, -1, -1):
		if text[i] in "[{":
			start = i
			open_ch = text[i]
			break
	if start is None:
		return None
	close_ch = "]" if open_ch == "[" else "}"
	depth = 0
	for j in range(start, len(text)):
		c = text[j]
		if c == open_ch:
			depth += 1
		elif c == close_ch:
			depth -= 1
			if depth == 0:
				return text[start : j + 1]
	return None


def _build_name_code_mapping(obj, mapping: dict):
	"""Recursively traverse parsed JSON and record {name: code} entries when found."""
	if isinstance(obj, dict):
		# if dict has both text and pro
		if "text" in obj and ("pro" in obj or "L" in obj):
			name = obj.get("text")
			code = obj.get("pro")
			lval = obj.get("L")
			if isinstance(name, str):
				entry = {}
				if code is not None:
					entry["pro"] = str(code)
				if lval is not None:
					entry["L"] = str(lval)
				if entry:
					mapping[name.strip().lower()] = entry
		for v in obj.values():
			_build_name_code_mapping(v, mapping)
	elif isinstance(obj, list):
		for it in obj:
			_build_name_code_mapping(it, mapping)


def get_name_code_mapping_from_page(url: str = START_URL, timeout: int = 15) -> dict:
	"""Fetch the page and try to extract JSON blobs containing 'text' and 'pro'.

	Returns mapping of normalized name -> code.
	"""
	text, resp = fetch(url, timeout=timeout)
	mapping = {}
	# search for occurrences of "\"text\"" and attempt to extract enclosing JSON
	idx = 0
	while True:
		idx = text.find('"text"', idx)
		if idx == -1:
			break
		# try extract enclosing JSON around this position
		js = _extract_enclosing_json(text, idx)
		if js:
			try:
				parsed = json.loads(js)
				_build_name_code_mapping(parsed, mapping)
			except Exception:
				pass
		idx += 6

	return mapping


def get_codes_for_names(input_path: str = "data/tenderbazar/product.json") -> list:
	"""Read names from input JSON and return list of codes found on the site.

	For each product name in the input (strings), returns the matched code or
	None if not found. Matching is case-insensitive and trimmed.
	"""
	import json

	with open(input_path, "r", encoding="utf-8") as f:
		data = json.load(f)

	# determine list of names in file
	names = []
	if isinstance(data, dict) and "products" in data and isinstance(data["products"], list):
		names = [n for n in data["products"] if isinstance(n, str)]
	elif isinstance(data, list):
		names = [n for n in data if isinstance(n, str)]
	else:
		# try to collect all string leaves
		def _collect_strings(o, out):
			if isinstance(o, str):
				out.append(o)
			elif isinstance(o, list):
				for it in o:
					_collect_strings(it, out)
			elif isinstance(o, dict):
				for v in o.values():
					_collect_strings(v, out)

		_collect_strings(data, names)

	mapping = get_name_code_mapping_from_page()

	results = []
	for n in names:
		key = n.strip().lower()
		entry = mapping.get(key)
		if entry:
			pro = entry.get("pro")
			lval = entry.get("L")
		else:
			pro = None
			lval = None
		results.append((n, pro, lval))

	return results


def fetch_tender_ids_for_pro(pro: str, lval: str | None = None, timeout: int = 15) -> list:
	"""Fetch the ResultByProduct pages for `pro` and return a list of tender IDs found.

	If `lval` is provided it is used to compute how many pages to fetch (10 items/page).
	"""
	import math, time

	def _parse_ids_from_html(text: str) -> list:
		soup = BeautifulSoup(text, "html.parser")
		ids_local = []
		for tr in soup.find_all("tr"):
			tds = tr.find_all("td")
			if not tds:
				continue
			first = tds[0].get_text(strip=True) if tds else ""
			if "Tender ID" in first:
				if len(tds) >= 3:
					td = tds[2]
					span = td.find("span", style=re.compile(r"float\s*:\s*left", re.I))
					if not span:
						span = td.find("span")
					if span:
						txt = span.get_text(strip=True)
						m = re.search(r"(\d+)", txt)
						if m:
							val = m.group(1)
							if val not in ids_local:
								ids_local.append(val)
		return ids_local

	ids = []
	ts = int(time.time() * 1000)
	first_url = f"{BASE_URL}/ListResult/ResultByProduct?no={pro}&type=L&_={ts}"
	text, resp = fetch(first_url, timeout=timeout)
	ids.extend(_parse_ids_from_html(text))

	total = None
	if lval:
		try:
			total = int(str(lval).strip())
		except Exception:
			total = None

	if total is None:
		# try to find an element in the page that indicates total count (heuristic)
		m = re.search(r"of\s+(\d+)\s+result", text, re.I)
		if m:
			try:
				total = int(m.group(1))
			except Exception:
				total = None

	if total is None:
		# fallback: if fewer than 10 results found, assume only one page
		if len(ids) < 10:
			return ids
		# otherwise attempt to fetch page 2 once to see if more exist
		total = None

	if total is not None and total > 10:
		pages = math.ceil(total / 10)
		# fetch pages 2..pages
		for p in range(2, pages + 1):
			ts = int(time.time() * 1000)
			page_url = f"{BASE_URL}/listresult/ResultByProduct?page={p}&order=1&no={pro}&type=L&pref=A&_={ts}"
			try:
				text, resp = fetch(page_url, timeout=timeout)
			except Exception:
				continue
			more_ids = _parse_ids_from_html(text)
			for mid in more_ids:
				if mid not in ids:
					ids.append(mid)

	return ids


def collect_all_tenders(input_path: str = "data/tenderbazar/product.json", output_path: str = "data/tenderbazar/tenders.json") -> None:
	"""For each product in input, fetch tender IDs and write results to output JSON.

	Output format: list of objects {"name": ..., "pro": ..., "L": ..., "tenders": [ids...]}
	"""
	pairs = get_codes_for_names(input_path)

	import os, json

	# load existing output if present
	existing = {}
	if os.path.exists(output_path):
		try:
			with open(output_path, "r", encoding="utf-8") as f:
				old = json.load(f)
			# index by pro if available, else by name
			for item in old:
				key = item.get("pro") or item.get("name")
				existing[key] = item
		except Exception:
			existing = {}

	updated_results = []
	total_new = 0
	changed_products = 0

	for name, pro, lval in pairs:
		key = pro or name
		prev = existing.get(key, {})
		prev_tenders = list(prev.get("tenders", [])) if isinstance(prev.get("tenders", []), list) else []

		# fetch current tenders
		ids = []
		if pro:
			try:
				ids = fetch_tender_ids_for_pro(pro, lval=lval)
			except Exception:
				ids = []

		# determine new ids not already in prev_tenders
		prev_set = set(prev_tenders)
		new_ids = [tid for tid in ids if tid not in prev_set]

		if new_ids:
			# append new ids to existing list
			merged = prev_tenders + new_ids
			total_new += len(new_ids)
			changed_products += 1
		else:
			merged = prev_tenders

		entry = {"name": name, "pro": pro, "L": lval, "tenders": merged}
		updated_results.append(entry)

	# also keep any existing entries that were not present in current pairs
	processed_keys = {item.get("pro") or item.get("name") for item in updated_results}
	for key, item in existing.items():
		if key not in processed_keys:
			updated_results.append(item)

	# ensure directory exists and write back
	outdir = os.path.dirname(output_path)
	if outdir and not os.path.exists(outdir):
		os.makedirs(outdir, exist_ok=True)
	with open(output_path, "w", encoding="utf-8") as f:
		json.dump(updated_results, f, ensure_ascii=False, indent=2)

	# prepare summary and changed entries
	changed_entries = []
	for name, pro, lval in pairs:
		key = pro or name
		prev = existing.get(key, {})
		prev_tenders = list(prev.get("tenders", [])) if isinstance(prev.get("tenders", []), list) else []
		# compute new ids that were added
		# find merged entry in updated_results
		merged = None
		for it in updated_results:
			if (it.get("pro") or it.get("name")) == key:
				merged = it
				break
		merged_tenders = merged.get("tenders", []) if merged else []
		new_ids = [tid for tid in merged_tenders if tid not in prev_tenders]
		if new_ids:
			changed_entries.append({"name": name, "pro": pro, "new_ids": new_ids})

	summary = {
		"total_products_checked": len(pairs),
		"products_with_new_tenders": changed_products,
		"total_new_tender_ids": total_new,
		"changed_entries": changed_entries,
		"output_path": output_path,
	}

	# print concise summary
	print(f"Total products checked: {summary['total_products_checked']}")
	print(f"Products with new tenders: {summary['products_with_new_tenders']}")
	print(f"Total new tender IDs added: {summary['total_new_tender_ids']}")

	return summary


def run(
	input_path: str = "data/tenderbazar/product.json",
	output_path: str = "data/tenderbazar/tenders.json",
) -> dict:
	"""Collect TenderBazar tenders and send configured notifications."""
	summary = collect_all_tenders(input_path=input_path, output_path=output_path)

	try:
		from notifications import email as notifier

		sent = notifier.send_update_notifications(summary)
		if sent:
			print("Notification email sent to users.")
		else:
			print("No notification sent (no updates or no recipients configured).")
	except Exception:
		print("Notifier failed or missing; skipping email send.")

	try:
		from notifications import telegram as notifier

		sent = notifier.send_update_notifications(summary)
		if sent:
			print("Telegram notification sent to users.")
		else:
			print("No Telegram notification sent (no updates or no chat IDs configured).")
	except Exception:
		print("Telegram notifier failed or missing; skipping Telegram send.")

	return summary


def _cli(argv: list[str] | None = None) -> int:
	p = argparse.ArgumentParser(description="Fetch TenderBazar products page and print the result")
	p.add_argument("--out", "-o", help="Write raw response bytes to file")
	p.add_argument("--raw", action="store_true", help="Force raw output (no JSON pretty-print)")
	p.add_argument("--timeout", type=int, default=15, help="Request timeout seconds")
	p.add_argument("--codes-file", help="Path to a local JSON file; extract and print all 'pro' codes from it")
	args = p.parse_args(argv)

	try:
		if args.codes_file:
			codes = extract_pro_codes(args.codes_file)
			for c in codes:
				print(c)
			return 0
		scrape_structured(out=args.out, raw=args.raw, timeout=args.timeout)
		return 0
	except requests.RequestException as exc:
		logging.error("Request failed: %s", exc)
		return 2


def extract_pro_codes(path: str) -> list:
	"""Load JSON from `path` and return a list of all values for keys named 'pro'."""
	import json

	with open(path, "r", encoding="utf-8") as f:
		data = json.load(f)
		print(f"Loaded JSON from {path}: {len(data)} top-level keys")

	codes: list = []

	def _recurse(obj):
		if isinstance(obj, dict):
			for k, v in obj.items():
				if k == "pro":
					codes.append(v)
				else:
					_recurse(v)
		elif isinstance(obj, list):
			for it in obj:
				_recurse(it)

	_recurse(data)
	return codes


if __name__ == "__main__":
	raise SystemExit(_cli())

