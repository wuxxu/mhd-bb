#!/usr/bin:env python3
"""Cross-check parsed JSON against PDF source using two independent methods.

We rely on a strong invariant of MHD timetables: every stop served by a trip
appears once in that trip's column. So for any direction:

    max(times across stops) == number of trips in that direction

We extract trip counts directly from the PDF (regex on trip-number rows) and
compare against the max time count per service in the JSON. This bypasses the
fragile leader-dot extraction in the time matrix and gives a robust upper-bound
check on data completeness.

Additionally, we sample a few specific (stop, time) tuples from the PDF text
and confirm they appear in the JSON.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pdfplumber

ROOT = Path(__file__).parent
PDF_DIR = ROOT / "pdfs"
JSON_DIR = ROOT.parent / "web" / "public" / "data" / "lines"


# ---- trip count extraction -------------------------------------------------


def parse_dpmbb_trips(pdf_path: Path) -> Dict[str, Dict[str, int]]:
    """For DPMBB PDFs, count trips per (direction, service).

    Direction: trip number parity (odd → forward, even → return).
    Service: trip number range (>=300 → weekend, else weekday).
    These are universal MHD BB conventions.
    """
    counts = {
        "forward": {"weekday": 0, "weekend": 0},
        "return": {"weekday": 0, "weekend": 0},
    }
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.split("\n"):
                if line.startswith("Tč"):
                    nums = [int(t) for t in re.findall(r"\b(\d+)\b", line) if int(t) <= 400]
                    for n in nums:
                        direction = "forward" if n % 2 == 1 else "return"
                        service = "weekend" if n >= 300 else "weekday"
                        counts[direction][service] += 1
    return counts


def parse_sadzv_trips(pdf_path: Path) -> Dict[str, Dict[str, int]]:
    """For SADZV PDFs, trip numbers don't carry weekday/weekend semantics —
    the day-type symbols (•/6/†) below the trip-number row do. We therefore
    cannot reliably classify by trip number alone. Instead, return TOTAL trips
    per direction; we'll check the sum of weekday + weekend in JSON matches.
    """
    counts = {
        "forward": 0,
        "return": 0,
    }
    current_dir = "forward"
    is_compact = False
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.split("\n"):
                if "opa" in line and "smer" in line:
                    current_dir = "return"
                # SADZV header includes "Tcˇ" (with caron). It can be at the start
                # of the line or in the middle for compact layouts.
                if "Tcˇ" in line or "Tč" in line:
                    # Strip the "Tcˇ" word and any preceding label text
                    parts = line.split()
                    digits = [p for p in parts if p.isdigit()]
                    nums = [int(d) for d in digits if int(d) <= 400]
                    if not nums:
                        continue
                    # Compact layout: Tcˇ in middle, both directions in same line
                    tcˇ_idx = next(
                        (i for i, p in enumerate(parts) if p == "Tcˇ" or p == "Tč"),
                        None,
                    )
                    if tcˇ_idx is not None and any(p.isdigit() for p in parts[:tcˇ_idx]):
                        is_compact = True
                        forward_nums = [int(p) for p in parts[:tcˇ_idx] if p.isdigit() and int(p) <= 400]
                        return_nums = [int(p) for p in parts[tcˇ_idx + 1:] if p.isdigit() and int(p) <= 400]
                        counts["forward"] += len(forward_nums)
                        counts["return"] += len(return_nums)
                    else:
                        counts[current_dir] += len(nums)
    counts["_compact"] = is_compact  # type: ignore[assignment]
    return counts


# ---- JSON max-time-count ---------------------------------------------------


def json_max_counts(line_no: str) -> List[Dict[str, int]]:
    """Return per-direction {weekday_max, weekend_max, weekday_min, weekend_min}."""
    data = json.loads((JSON_DIR / f"{line_no}.json").read_text())
    out = []
    for direction in data["directions"]:
        wd_counts = [len(s["times"]["weekday"]) for s in direction["stops"]]
        we_counts = [len(s["times"]["weekend"]) for s in direction["stops"]]
        out.append(
            {
                "headsign": direction["headsign"],
                "stops": len(direction["stops"]),
                "weekday_max": max(wd_counts) if wd_counts else 0,
                "weekday_min": min(wd_counts) if wd_counts else 0,
                "weekend_max": max(we_counts) if we_counts else 0,
                "weekend_min": min(we_counts) if we_counts else 0,
            }
        )
    return out


# ---- spot-check -----------------------------------------------------------


def spot_check_dpmbb(line_no: str, sample_count: int = 4) -> List[Tuple[str, str, str, bool, str]]:
    """Pull random clean HH.MM tokens from the PDF text and verify they are
    present in the JSON for some stop. Returns list of (stop_name, service_guess, time, found, notes).

    For DPMBB, every clean HH.MM in a stop row should appear in that stop's
    times list (in the matching direction).
    """
    pdf_path = PDF_DIR / f"linka_{line_no}.pdf"
    data = json.loads((JSON_DIR / f"{line_no}.json").read_text())

    # Build a lookup: stop_name -> set of all times (across both directions, both services)
    all_times: Dict[str, Set[str]] = {}
    for direction in data["directions"]:
        for stop in direction["stops"]:
            n = stop["name"]
            all_times.setdefault(n, set()).update(stop["times"]["weekday"])
            all_times[n].update(stop["times"]["weekend"])

    samples: List[Tuple[str, str, str, bool, str]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.split("\n"):
                # Match a stop row: starts with stop num, then optional od/pr, then name, leader dots
                m = re.match(r"^\s*(\d{1,2})\s*(?:od|pr)?\s*(.+?)\s*\.{4,}", line)
                if not m:
                    continue
                stop_num = int(m.group(1))
                if not (1 <= stop_num <= 30):
                    continue
                stop_name = m.group(2).strip()
                # Strip glued "od"/"pr" prefix (e.g. "odŽelezničná")
                stop_name = re.sub(r"^(od|pr)(?=[A-ZČŠŽĎŤĽĹŔÁÉÍÓÚÝÄÔ])", "", stop_name)
                # Find clean times in the line
                clean_times = re.findall(r"\b(\d{2})\.(\d{2})\b", line)
                if not clean_times:
                    continue
                # Take a random-ish sample (every 7th time, capped)
                step = max(1, len(clean_times) // sample_count)
                picks = clean_times[::step][:sample_count]
                for h, mm in picks:
                    t = f"{int(h):02d}:{int(mm):02d}"
                    candidates = all_times.get(stop_name, set())
                    found = t in candidates
                    samples.append((stop_name, "any", t, found, ""))
    return samples


def spot_check_sadzv(line_no: str) -> List[Tuple[str, str, bool, str]]:
    """For SADZV format, do a structural check: find rows that have stop name
    + extract any HH MM pairs and verify they appear in JSON.
    Returns (stop_name, time, found, raw_context).
    """
    pdf_path = PDF_DIR / f"linka_{line_no}.pdf"
    data = json.loads((JSON_DIR / f"{line_no}.json").read_text())

    all_times: Dict[str, Set[str]] = {}
    for direction in data["directions"]:
        for stop in direction["stops"]:
            n = stop["name"]
            all_times.setdefault(n, set()).update(stop["times"]["weekday"])
            all_times[n].update(stop["times"]["weekend"])

    # Use char-level extraction so we get precise H/MM pairs, similar to the parser.
    from collections import defaultdict
    samples: List[Tuple[str, str, bool, str]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(keep_blank_chars=False)
            rows: Dict[int, list] = defaultdict(list)
            for w in words:
                rows[round(w["top"])].append(w)
            for y in sorted(rows.keys()):
                row = sorted(rows[y], key=lambda w: w["x0"])
                if not row:
                    continue
                # Stop row starts with a small int and has alpha words after
                first = row[0]["text"]
                if not (first.isdigit() and 1 <= int(first) <= 30):
                    continue
                # Compose stop name from alpha words at low x (compact: medium x)
                # Look for words containing letters until x > 200 (non-compact) or until a digit-only word
                alpha_re = re.compile(
                    r"[A-Za-záéíóúýčďňšťžľĺŕäôÁÉÍÓÚÝČĎŇŠŤŽĽĹŔÄÔ]"
                )
                name_words: List[str] = []
                for w in row[1:8]:
                    t = w["text"]
                    if alpha_re.search(t) and t not in ("od", "pr", "WC"):
                        # Apply ligature fixes
                        t = (
                            t.replace("cˇ", "č").replace("Cˇ", "Č")
                            .replace("dˇ", "ď").replace("Dˇ", "Ď")
                            .replace("nˇ", "ň").replace("Nˇ", "Ň")
                            .replace("tˇ", "ť").replace("Tˇ", "Ť")
                            .replace("l’", "ľ").replace("L’", "Ľ")
                        )
                        name_words.append(t)
                    elif name_words:
                        break
                if not name_words:
                    continue
                stop_name = " ".join(name_words)
                # Match against JSON stops by suffix containment to handle minor name variations
                matched_key = None
                for k in all_times:
                    if k == stop_name or stop_name.endswith(k) or k.endswith(stop_name):
                        matched_key = k
                        break
                if not matched_key:
                    continue
                # SADZV times: collect digits from this row (and nearby rows for split-digit cells)
                # Combine words in pairs that look like H + MM
                tokens = [w["text"] for w in row[1:] if not alpha_re.search(w["text"]) and w["text"] != "..."]
                # Walk tokens left to right, grouping (1-2 digit) + (2 digit) pairs
                times_found: List[str] = []
                i = 0
                current_hour: Optional[int] = None
                while i < len(tokens):
                    t = tokens[i]
                    digits = re.sub(r"\D", "", t)
                    if not digits:
                        i += 1
                        continue
                    if len(digits) >= 4:
                        # Maybe it's a merged "HHMM" pair already
                        h = int(digits[:2])
                        mm = int(digits[2:4])
                        if 0 <= h <= 23 and 0 <= mm <= 59:
                            times_found.append(f"{h:02d}:{mm:02d}")
                            current_hour = h
                        i += 1
                    elif len(digits) <= 2 and i + 1 < len(tokens):
                        # Look ahead for minute companion
                        next_digits = re.sub(r"\D", "", tokens[i + 1])
                        if len(next_digits) == 2 and 0 <= int(next_digits) <= 59 and 0 <= int(digits) <= 23:
                            h = int(digits)
                            mm = int(next_digits)
                            if h <= 23:
                                times_found.append(f"{h:02d}:{mm:02d}")
                                current_hour = h
                            i += 2
                            continue
                        elif len(digits) == 2 and current_hour is not None and 0 <= int(digits) <= 59:
                            times_found.append(f"{current_hour:02d}:{int(digits):02d}")
                        i += 1
                    else:
                        i += 1
                # Sample 4 times spread across the row
                if not times_found:
                    continue
                step = max(1, len(times_found) // 4)
                picks = times_found[::step][:4]
                candidates = all_times.get(matched_key, set())
                for t in picks:
                    samples.append((matched_key, t, t in candidates, ""))
    return samples


# ---- main ------------------------------------------------------------------


def detect_format(pdf_path: Path) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        text = pdf.pages[0].extract_text() or ""
    if "DPM BB" in text or "Dopravný podnik" in text:
        return "DPMBB"
    return "SADZV"


def validate_line(line_no: str) -> None:
    pdf_path = PDF_DIR / f"linka_{line_no}.pdf"
    fmt = detect_format(pdf_path)
    json_dirs = json_max_counts(line_no)

    print(f"\n=== LINKA {line_no} ({fmt}) ===")
    for d in json_dirs:
        print(
            f"  → {d['headsign']:35s} stops={d['stops']:2d}  "
            f"wd: {d['weekday_min']:>2d}–{d['weekday_max']:<2d}  "
            f"we: {d['weekend_min']:>2d}–{d['weekend_max']:<2d}"
        )

    if fmt == "DPMBB":
        trips = parse_dpmbb_trips(pdf_path)
        # Each direction's max time count should be ≈ trip count. For loop routes
        # (a stop visited twice per trip, like "Ďumbierska ZŠ" on linka 20) the
        # max can legitimately reach 2× trip count; we accept this with a note.
        for i, label in enumerate(["forward", "return"]):
            if i >= len(json_dirs):
                continue
            d = json_dirs[i]
            t = trips[label]

            def status(actual: int, expected: int) -> str:
                if expected == 0:
                    return "✓" if actual == 0 else "✗"
                # Allow 0.6× to 2.05× (route variants ↔ loop routes)
                if 0.6 * expected <= actual <= 2.05 * expected:
                    note = " (loop)" if actual > expected else ""
                    return f"✓{note}"
                return "✗"

            print(
                f"  PDF trips {label}: wd={t['weekday']} (JSON max {d['weekday_max']} {status(d['weekday_max'], t['weekday'])}), "
                f"we={t['weekend']} (JSON max {d['weekend_max']} {status(d['weekend_max'], t['weekend'])})"
            )
        # Spot-check times
        samples = spot_check_dpmbb(line_no)
        misses = [s for s in samples if not s[3]]
        print(
            f"  Spot-check: {len(samples) - len(misses)}/{len(samples)} sampled times "
            f"present in JSON"
        )
        if misses[:3]:
            print(f"    misses: {[(s[0], s[2]) for s in misses[:3]]}")
    else:
        trips = parse_sadzv_trips(pdf_path)
        if trips.get("_compact"):
            total = trips["forward"] + trips["return"]
            print(f"  PDF compact layout: forward={trips['forward']}, return={trips['return']} (total {total})")
        else:
            for i, label in enumerate(["forward", "return"]):
                if i >= len(json_dirs):
                    continue
                d = json_dirs[i]
                expected_total = trips[label]
                actual_total = d["weekday_max"] + d["weekend_max"]
                # Tolerance: route variants can leave a stop with slightly fewer
                # trips than the total (each trip may skip 1-2 stops). Loop routes
                # can stop at the same name twice, doubling the max. Accept the
                # range [0.6*expected, 2.05*expected].
                ok = 0.6 * expected_total <= actual_total <= 2.05 * expected_total
                note = " (loop)" if actual_total > expected_total else ""
                mark = f"✓{note}" if ok else "✗"
                print(
                    f"  PDF trips {label}: total={expected_total} | "
                    f"JSON max wd={d['weekday_max']} + we={d['weekend_max']} = "
                    f"{actual_total} {mark}"
                )
        samples = spot_check_sadzv(line_no)
        misses = [s for s in samples if not s[2]]
        print(
            f"  Spot-check: {len(samples) - len(misses)}/{len(samples)} sampled times "
            f"present in JSON"
        )
        if misses[:5]:
            print(f"    misses: {[(s[0][:30], s[1]) for s in misses[:5]]}")


if __name__ == "__main__":
    lines = sys.argv[1:] or ["1", "4", "21", "29", "42"]
    for ln in lines:
        validate_line(ln)
