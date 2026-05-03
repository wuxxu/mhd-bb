#!/usr/bin/env python3
"""Cross-check parsed JSON against imhd.sk's HTML timetables.

imhd.sk pulls from a different source/format and renders weekday and weekend
schedules directly into HTML. If both our parser and imhd.sk agree on a
stop's departure list, we have very high confidence the data is correct.

We don't fetch every stop (rate-limit politeness) — just a sample covering
DPMBB, SADZV standard, and SADZV compact lines.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import requests

ROOT = Path(__file__).parent
JSON_DIR = ROOT.parent / "web" / "public" / "data" / "lines"

LISTING_URL = "https://imhd.sk/bb/cestovne-poriadky"
SESSION = requests.Session()
SESSION.headers["User-Agent"] = "Mozilla/5.0 (mhd-bb cross-checker)"

LINE_HREF_RE = re.compile(r'href="(/bb/linka/(\d+)/[a-f0-9]+)"')
STOP_HREF_RE = re.compile(
    r'href="(/bb/cestovny-poriadok/linka/(\d+)/([^/]+)/smer-([^/]+)/[a-f0-9]+)"'
)
TIMETABLE_ROW_RE = re.compile(
    r'<tr id="sm(\d+)T(\d+)"[^>]*>(.*?)</tr>',
    re.DOTALL,
)
MINUTE_TD_RE = re.compile(r'<td[^>]*data-depid="\d+"[^>]*>(\d+)</td>')


def get_line_index() -> Dict[str, str]:
    """Map line number → relative line URL on imhd.sk."""
    r = SESSION.get(LISTING_URL, timeout=20)
    r.raise_for_status()
    out = {}
    for m in LINE_HREF_RE.finditer(r.text):
        url, line = m.group(1), m.group(2)
        out.setdefault(line, url)
    return out


def get_stop_pages(line_url: str) -> List[Dict[str, str]]:
    """Return a list of {line, stop, direction, url} entries for the line page."""
    r = SESSION.get(f"https://imhd.sk{line_url}", timeout=20)
    r.raise_for_status()
    seen: Set[str] = set()
    pages = []
    for m in STOP_HREF_RE.finditer(r.text):
        url = m.group(1)
        if url in seen:
            continue
        seen.add(url)
        pages.append(
            {
                "line": m.group(2),
                "stop": urllib.parse.unquote(m.group(3)),
                "direction": urllib.parse.unquote(m.group(4)),
                "url": url,
            }
        )
    return pages


SERVICE_LABEL_RE = re.compile(
    r'id="SM-(\d+)-tab"[^>]*>([^<]+)</a>'
)


def fetch_schedule_times(stop_url: str) -> Tuple[Dict[str, Set[str]], Dict[str, str]]:
    """Fetch a single stop schedule page and extract per-service times.

    Returns (times_by_service_id, service_id_to_label_map).
    Each numeric service id (e.g. 113, 127) maps to a Slovak label like
    "Pracovné dni" or "Voľné dni" that we use for weekday/weekend classification.
    """
    r = SESSION.get(f"https://imhd.sk{stop_url}", timeout=20)
    r.raise_for_status()
    times_by_service: Dict[str, Set[str]] = {}
    for m in TIMETABLE_ROW_RE.finditer(r.text):
        service_id = m.group(1)
        hour = int(m.group(2))
        body = m.group(3)
        for mm in MINUTE_TD_RE.finditer(body):
            minute = int(mm.group(1))
            t = f"{hour:02d}:{minute:02d}"
            times_by_service.setdefault(service_id, set()).add(t)
    labels = {m.group(1): m.group(2).strip() for m in SERVICE_LABEL_RE.finditer(r.text)}
    return times_by_service, labels


def classify_service(label: str) -> str:
    """Map imhd.sk's Slovak service-mode label to our weekday/weekend bucket."""
    s = label.lower()
    if "pracovn" in s:
        return "weekday"
    if "voľn" in s or "volne" in s or "víkend" in s or "vikend" in s or "sobot" in s or "nedeľ" in s or "nedel" in s:
        return "weekend"
    return "other"


def normalise_stop_name(name: str) -> str:
    """imhd.sk uses dashes-as-spaces in URLs and drops punctuation; our JSON
    keeps original Slovak names with commas, periods, etc. Reduce both to a
    common alphanumeric-only form for fuzzy matching."""
    s = name.replace("-", " ").lower()
    s = re.sub(r"[^a-z0-9áéíóúýčďňšťžľĺŕäô ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def find_json_stop(line_no: str, stop_name_imhd: str, direction_imhd: str):
    """Locate a stop in our JSON whose name approximately matches imhd.sk's
    stop URL slug. Returns the stop dict or None."""
    data = json.loads((JSON_DIR / f"{line_no}.json").read_text())
    target = normalise_stop_name(stop_name_imhd)
    direction_target = normalise_stop_name(direction_imhd)
    best = None
    for direction in data["directions"]:
        # We don't strictly require headsign match — imhd's "smer" can disagree
        # with our parser's "last stop in route order". But prefer matches.
        dir_match = direction_target in normalise_stop_name(direction["headsign"])
        for stop in direction["stops"]:
            if normalise_stop_name(stop["name"]) == target:
                if dir_match:
                    return stop
                if best is None:
                    best = stop
    return best


def compare(line_no: str, sample_stops: int = 4) -> dict:
    line_index = get_line_index()
    if line_no not in line_index:
        return {"line": line_no, "error": "not in imhd listing"}
    line_url = line_index[line_no]
    pages = get_stop_pages(line_url)
    if not pages:
        return {"line": line_no, "error": "no stop pages found"}

    # Pick a spread sample: first, last, and a few middle stops
    if len(pages) <= sample_stops:
        sampled = pages
    else:
        step = max(1, len(pages) // sample_stops)
        sampled = pages[::step][:sample_stops]

    results = []
    for entry in sampled:
        time.sleep(0.4)  # be polite
        try:
            imhd_times, labels = fetch_schedule_times(entry["url"])
        except Exception as e:
            results.append({**entry, "error": str(e)})
            continue
        # Aggregate by service category — using the human label, not the numeric ID
        imhd_by_cat: Dict[str, Set[str]] = {"weekday": set(), "weekend": set()}
        for sid, times in imhd_times.items():
            label = labels.get(sid, "")
            cat = classify_service(label)
            if cat in imhd_by_cat:
                imhd_by_cat[cat].update(times)

        json_stop = find_json_stop(line_no, entry["stop"], entry["direction"])
        if not json_stop:
            results.append({**entry, "error": "no matching stop in JSON", "imhd_wd": len(imhd_by_cat["weekday"])})
            continue

        json_wd = set(json_stop["times"]["weekday"])
        json_we = set(json_stop["times"]["weekend"])

        results.append(
            {
                "stop": entry["stop"],
                "direction": entry["direction"],
                "matched_json_stop": json_stop["name"],
                "imhd_wd": len(imhd_by_cat["weekday"]),
                "json_wd": len(json_wd),
                "wd_only_imhd": sorted(imhd_by_cat["weekday"] - json_wd)[:5],
                "wd_only_json": sorted(json_wd - imhd_by_cat["weekday"])[:5],
                "imhd_we": len(imhd_by_cat["weekend"]),
                "json_we": len(json_we),
                "we_only_imhd": sorted(imhd_by_cat["weekend"] - json_we)[:5],
                "we_only_json": sorted(json_we - imhd_by_cat["weekend"])[:5],
            }
        )

    return {"line": line_no, "stops": results}


def report(result: dict) -> None:
    print(f"\n=== LINKA {result['line']} ===")
    if "error" in result:
        print(f"  ERROR: {result['error']}")
        return
    for s in result["stops"]:
        if "error" in s:
            print(f"  ✗ {s.get('stop', '?')[:25]}: {s['error']}")
            continue
        wd_match = (s["imhd_wd"] == s["json_wd"]) and not s["wd_only_imhd"] and not s["wd_only_json"]
        we_match = (s["imhd_we"] == s["json_we"]) and not s["we_only_imhd"] and not s["we_only_json"]
        wd_mark = "✓" if wd_match else "✗"
        we_mark = "✓" if we_match else "✗"
        print(
            f"  {s['stop'][:30]:30s} → {s['direction'][:25]:25s}  "
            f"wd: imhd={s['imhd_wd']:>3d} json={s['json_wd']:>3d} {wd_mark}  "
            f"we: imhd={s['imhd_we']:>3d} json={s['json_we']:>3d} {we_mark}"
        )
        if not wd_match:
            if s["wd_only_imhd"]:
                print(f"    weekday only in imhd: {s['wd_only_imhd']}")
            if s["wd_only_json"]:
                print(f"    weekday only in json: {s['wd_only_json']}")
        if not we_match:
            if s["we_only_imhd"]:
                print(f"    weekend only in imhd: {s['we_only_imhd']}")
            if s["we_only_json"]:
                print(f"    weekend only in json: {s['we_only_json']}")


if __name__ == "__main__":
    lines = sys.argv[1:] or ["1", "4", "21", "29", "42", "100"]
    for ln in lines:
        report(compare(ln))
