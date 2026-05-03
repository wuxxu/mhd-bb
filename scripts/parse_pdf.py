#!/usr/bin/env python3
"""Parse DPMBB / SAD-ZV bus timetable PDFs into JSON.

Output schema:
{
  "line": "1",
  "name": "Železničná stanica - Rooseveltova nemocnica a späť",
  "operator": "DPMBB" | "SADZV",
  "validFrom": "2025-12-14",
  "directions": [
    {
      "headsign": "Rooseveltova nemocnica",
      "stops": [
        {"name": "...", "times": {"weekday": [...], "weekend": [...]}}
      ]
    }
  ]
}
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pdfplumber

WEEKDAY = "weekday"
WEEKEND = "weekend"

# Stop "marker" chars (od/pr/down-arrow/etc.)
STOP_MARKER_TOKENS = {"od", "pr", "‰", "fl", "▼", "▲"}


def normalise_time(token: str) -> Optional[str]:
    digits = re.sub(r"\D", "", token)
    if len(digits) == 3:
        h, m = int(digits[0]), int(digits[1:])
    elif len(digits) == 4:
        h, m = int(digits[:2]), int(digits[2:])
    else:
        return None
    if 0 <= h <= 23 and 0 <= m <= 59:
        return f"{h:02d}:{m:02d}"
    return None


def cluster_rows(items: list, key: str = "top", tol: float = 3.0) -> Dict[float, list]:
    """Group items (chars or words) into rows by y-coordinate."""
    if not items:
        return {}
    items_sorted = sorted(items, key=lambda it: it[key])
    clusters: List[List[dict]] = [[items_sorted[0]]]
    for it in items_sorted[1:]:
        if it[key] - clusters[-1][-1][key] <= tol:
            clusters[-1].append(it)
        else:
            clusters.append([it])
    out: Dict[float, list] = {}
    for cl in clusters:
        centre = round(sum(it[key] for it in cl) / len(cl))
        out[centre] = cl
    return out


def assign_column(x: float, columns: List[float], tol: float = 12.0) -> Optional[int]:
    """Nearest-column assignment with absolute tolerance — used for header symbols
    (workday bullets, day-type markers) where overshoot is rare."""
    best_idx, best_dist = None, tol
    for i, cx in enumerate(columns):
        d = abs(x - cx)
        if d < best_dist:
            best_idx, best_dist = i, d
    return best_idx


def assign_column_by_boundaries(
    x: float, boundaries: List[float], n_columns: int
) -> Optional[int]:
    """Assign x to a column using midpoint boundaries.

    ``boundaries[i]`` is the right-edge of column i (i.e., the midpoint between
    trip-number x[i] and x[i+1]). The last column has no right boundary; chars
    beyond ``boundaries[-1]`` fall into the last column. Chars before the first
    trip-number x are rejected (likely stop-name leakage).
    """
    if not boundaries:
        return 0 if n_columns else None
    # Walk boundaries in order; first boundary > x means we're in column i.
    for i, b in enumerate(boundaries):
        if x <= b:
            return i
    return n_columns - 1


def compute_column_boundaries(
    columns: List[float], column_ends: Optional[List[float]] = None
) -> List[float]:
    """Right-edge boundaries between adjacent columns. Returned list has length
    ``len(columns) - 1``; index i is the right edge of column i.

    Time digits in SADZV cells are RIGHT-aligned to the trip number's centre
    (so a 2-digit hour like "11" sits with its right edge near the centre of a
    2-digit trip number like "15"). The cell boundary is therefore best placed
    at the midpoint between the **centres** of adjacent trip numbers, not at
    the midpoint of their left edges. When ``column_ends`` is missing, falls
    back to averaging trip number x0 positions.
    """
    if column_ends is None:
        return [(a + b) / 2.0 for a, b in zip(columns, columns[1:])]
    centres = [(x0 + x1) / 2.0 for x0, x1 in zip(columns, column_ends)]
    return [(centres[i] + centres[i + 1]) / 2.0 for i in range(len(centres) - 1)]


def column_tol(columns: List[float], default: float = 12.0) -> float:
    """Half the minimum adjacent column gap, capped at ``default``. Used as a
    sanity tolerance for service-marker assignment.
    """
    if len(columns) < 2:
        return default
    sorted_cols = sorted(columns)
    gaps = [b - a for a, b in zip(sorted_cols, sorted_cols[1:])]
    return max(4.0, min(default, min(gaps) / 2 - 0.5))


# ---- DPMBB parser ----------------------------------------------------------


def parse_dpmbb(pdf_path: Path) -> dict:
    line_no, name, valid_from = "", "", ""
    forward: Dict[str, Dict[str, List[str]]] = {}
    forward_order: List[str] = []
    return_: Dict[str, Dict[str, List[str]]] = {}
    return_order: List[str] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if page_idx == 0:
                m = re.search(
                    r"\b(\d+)\s+(.*?)\s+a\s+späť\s+Platí od:\s*(\d{1,2})\.(\d{1,2})\.(\d{4})",
                    text,
                )
                if not m:
                    m = re.search(
                        r"\b(\d+)\s+(.*?)\s+Platí od:\s*(\d{1,2})\.(\d{1,2})\.(\d{4})",
                        text,
                    )
                if m:
                    line_no = m.group(1)
                    name = m.group(2).strip().replace("\n", " ")
                    d, mo, y = m.group(3), m.group(4), m.group(5)
                    valid_from = f"{y}-{int(mo):02d}-{int(d):02d}"

            words = page.extract_words(keep_blank_chars=False)
            chars = page.chars
            word_rows = cluster_rows(words, key="top", tol=3.0)
            char_rows = cluster_rows(chars, key="top", tol=3.0)
            sorted_word_ys = sorted(word_rows.keys())

            # Iterate Tč header blocks
            i = 0
            while i < len(sorted_word_ys):
                y = sorted_word_ys[i]
                row = sorted(word_rows[y], key=lambda w: w["x0"])
                if not row or row[0]["text"] != "Tč":
                    i += 1
                    continue

                # Trip numbers: digits in this row to the right of x>180
                trip_cols: List[Tuple[float, str]] = []
                for w in row:
                    if w["text"].isdigit() and w["x0"] > 180:
                        trip_cols.append((w["x0"], w["text"]))
                if not trip_cols:
                    i += 1
                    continue

                column_xs = [c[0] for c in trip_cols]
                trip_numbers = [int(c[1]) for c in trip_cols]
                # Direction is determined by trip number parity, a universal MHD BB
                # convention: odd trip numbers → forward, even → return. This avoids
                # having to track per-page "opačný smer" markers (which can appear
                # multiple times on heavily-paginated lines like 6 or 7).
                column_directions = [
                    "forward" if n % 2 == 1 else "return" for n in trip_numbers
                ]
                service_codes = ["?"] * len(trip_cols)

                # Walk rows below the header, accumulating service codes from rows that
                # are NOT yet stop-data rows. A stop-data row begins with a small int
                # at x≈45 followed by a stop name word.
                j = i + 1
                while j < len(sorted_word_ys):
                    ry = sorted_word_ys[j]
                    rrow = sorted(word_rows[ry], key=lambda w: w["x0"])
                    if not rrow:
                        j += 1
                        continue
                    ft = rrow[0]["text"]
                    ft_x = rrow[0]["x0"]
                    if ft.isdigit() and ft_x < 60 and len(rrow) > 1:
                        # Looks like start of stop data
                        break
                    # Otherwise treat as code/marker row
                    for w in rrow:
                        ci = assign_column(w["x0"], column_xs, tol=14)
                        if ci is None:
                            continue
                        t = w["text"]
                        # PDF may merge vertically stacked E/X into "EX" or "XE"
                        if "E" in t or "X" in t:
                            if service_codes[ci] == "?":
                                service_codes[ci] = ""
                            service_codes[ci] += t
                    j += 1

                # Resolve service per column, prefer trip number range as authority
                service_per_col: List[str] = []
                for ci in range(len(trip_cols)):
                    code = service_codes[ci]
                    tn = trip_numbers[ci]
                    if tn >= 300:
                        service_per_col.append(WEEKEND)
                    elif "E" in code:
                        service_per_col.append(WEEKEND)
                    else:
                        service_per_col.append(WEEKDAY)

                # Now walk stop-data rows
                while j < len(sorted_word_ys):
                    ry = sorted_word_ys[j]
                    rrow = sorted(word_rows[ry], key=lambda w: w["x0"])
                    if not rrow:
                        j += 1
                        continue
                    ft = rrow[0]["text"]
                    ft_x = rrow[0]["x0"]
                    # Stop section ends when we hit a new Tč header or legend ("X -")
                    if ft == "Tč":
                        break
                    if ft in ("X", "E", "†") and ft_x < 60 and len(rrow) >= 2:
                        # Legend line: "X - premáva v ..." — skip and continue (could end of block)
                        j += 1
                        continue
                    if ft.startswith(("pokračovanie", "opačný", "Predkladá", "Schvaľuje", "Linka", "Vytlačené")):
                        j += 1
                        continue
                    # Stop-data rows: small int 1-30 at x<60
                    if not (ft.isdigit() and ft_x < 60 and 1 <= int(ft) <= 50):
                        j += 1
                        continue

                    # Stop name: words after the stop number, before x>180
                    name_parts: List[str] = []
                    for w in rrow[1:]:
                        if w["x0"] >= 200:
                            break
                        t = w["text"]
                        if t.startswith("."):
                            continue
                        if t in STOP_MARKER_TOKENS:
                            continue
                        # Word might be glued like "odŽelezničná" — strip leading od/pr
                        for prefix in ("od", "pr"):
                            if t.startswith(prefix) and len(t) > len(prefix) and t[len(prefix)].isupper():
                                t = t[len(prefix):]
                                break
                        if t:
                            name_parts.append(t)
                    stop_name = " ".join(name_parts).strip()

                    # Get all chars in rows ±tolerance around ry
                    relevant_chars = []
                    for cy in char_rows.keys():
                        if abs(cy - ry) <= 4:
                            relevant_chars.extend(char_rows[cy])

                    # Bin chars to columns
                    cell_chars: Dict[int, List[dict]] = defaultdict(list)
                    for c in relevant_chars:
                        # ignore chars far left (stop name)
                        if c["x0"] < column_xs[0] - 25:
                            continue
                        ci = assign_column(c["x0"], column_xs, tol=12)
                        if ci is not None:
                            cell_chars[ci].append(c)

                    times: List[Optional[str]] = []
                    for ci in range(len(column_xs)):
                        cs = sorted(cell_chars.get(ci, []), key=lambda c: c["x0"])
                        raw = "".join(c["text"] for c in cs)
                        times.append(normalise_time(raw))

                    # Some times are missing because they got merged into the leader-dot
                    # cell at x ≈ 130-200. Recover them: for each column from left that's
                    # missing, look at the leader-cell digits.
                    leader_chars = sorted(
                        [c for c in relevant_chars if 120 <= c["x0"] < column_xs[0] - 5 and c["text"] != "."],
                        key=lambda c: c["x0"],
                    )
                    leader_text = "".join(c["text"] for c in leader_chars)
                    leader_digits = re.sub(r"\D", "", leader_text)

                    # Each missing leftmost time consumes 4 digits (HHMM) from leader.
                    consumed = 0
                    for ci in range(len(times)):
                        if times[ci] is None and consumed + 4 <= len(leader_digits):
                            t = normalise_time(leader_digits[consumed : consumed + 4])
                            if t:
                                times[ci] = t
                                consumed += 4
                            else:
                                break
                        else:
                            # Once we hit a column with a clean time, stop trying to fill from leader
                            break

                    # Store. Direction is per-column (from trip number parity), so a
                    # single block can technically contribute to both directions,
                    # though in practice DPMBB always has homogeneous parity per block.
                    if stop_name:
                        for ci, t in enumerate(times):
                            if t is None:
                                continue
                            direction = column_directions[ci] if ci < len(column_directions) else "forward"
                            target = forward if direction == "forward" else return_
                            order = forward_order if direction == "forward" else return_order
                            if stop_name not in target:
                                target[stop_name] = {WEEKDAY: [], WEEKEND: []}
                                order.append(stop_name)
                            svc = service_per_col[ci] if ci < len(service_per_col) else WEEKDAY
                            target[stop_name][svc].append(t)

                    j += 1

                i = j

    def build_direction(target, order):
        if not order:
            return None
        nonempty = [
            s for s in order
            if target[s][WEEKDAY] or target[s][WEEKEND]
        ]
        if not nonempty:
            return None
        return {
            "headsign": nonempty[-1],
            "stops": [
                {
                    "name": s,
                    "times": {
                        WEEKDAY: sorted(set(target[s][WEEKDAY])),
                        WEEKEND: sorted(set(target[s][WEEKEND])),
                    },
                }
                for s in nonempty
            ],
        }

    directions = []
    fwd = build_direction(forward, forward_order)
    if fwd:
        directions.append(fwd)
    ret = build_direction(return_, return_order)
    if ret:
        directions.append(ret)

    return {
        "line": line_no,
        "name": name,
        "operator": "DPMBB",
        "validFrom": valid_from,
        "directions": directions,
    }


# ---- SADZV parser ----------------------------------------------------------


# SADZV uses bullet (•, encoded as cid:1 in some fonts) for workday, "6" digit for
# Saturday, "†" for Sunday/holiday. A single column may carry multiple symbols
# meaning the trip runs on multiple service types.
SADZV_WEEKDAY_TOKENS = {"(cid:1)", "•", "•"}
SADZV_SATURDAY_TOKENS = {"6"}
SADZV_SUNDAY_TOKENS = {"†", "†"}


def parse_sadzv(pdf_path: Path) -> dict:
    line_no, name, valid_from = "", "", ""
    forward: Dict[str, Dict[str, List[str]]] = {}
    forward_order: List[str] = []
    return_: Dict[str, Dict[str, List[str]]] = {}
    return_order: List[str] = []
    compact_seen = False

    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if page_idx == 0:
                # First line: "20 Parkovisko Mičinská-Autobusová..."
                m = re.search(r"^\s*(\d+)\s+(.+?)\s*$", text.split("\n")[0])
                if m:
                    line_no = m.group(1)
                    # Combine line title from first 1-2 lines until "Platí od"
                    title_lines = []
                    for ln in text.split("\n"):
                        if "Platí" in ln or "Prepravu" in ln:
                            break
                        title_lines.append(ln.strip())
                    full_title = " ".join(title_lines).strip()
                    # Strip leading line number
                    full_title = re.sub(r"^\d+\s+", "", full_title)
                    # Fix the cˇ ligature (caron + c) -> č
                    full_title = full_title.replace("cˇ", "č").replace("Cˇ", "Č")
                    full_title = full_title.replace("dˇ", "ď").replace("Dˇ", "Ď")
                    full_title = full_title.replace("nˇ", "ň").replace("Nˇ", "Ň")
                    full_title = full_title.replace("tˇ", "ť").replace("Tˇ", "Ť")
                    full_title = full_title.replace("l’", "ľ").replace("L’", "Ľ")
                    name = full_title
                m2 = re.search(r"Platí od\s*(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
                if m2:
                    d, mo, y = m2.group(1), m2.group(2), m2.group(3)
                    valid_from = f"{y}-{int(mo):02d}-{int(d):02d}"

            words = page.extract_words(keep_blank_chars=False)
            chars = page.chars
            word_rows = cluster_rows(words, key="top", tol=2.5)
            sorted_word_ys = sorted(word_rows.keys())

            opacny_y = None
            for y in sorted_word_ys:
                row = sorted(word_rows[y], key=lambda w: w["x0"])
                row_text = " ".join(w["text"] for w in row).lower()
                if row_text.startswith("opa") and "smer" in row_text:
                    opacny_y = y
                    break

            i = 0
            while i < len(sorted_word_ys):
                y = sorted_word_ys[i]
                row = sorted(word_rows[y], key=lambda w: w["x0"])
                if not row:
                    i += 1
                    continue
                # SADZV header keyword: "Tcˇ" (or any "Tc"-starting at small width).
                # Find it ANYWHERE in the row — compact layouts have it in the middle.
                tcˇ_word = None
                for w in row:
                    if w["text"].startswith("Tc") or w["text"] == "Tč":
                        tcˇ_word = w
                        break
                if tcˇ_word is None:
                    i += 1
                    continue

                tcˇ_x = tcˇ_word["x0"]
                is_compact = tcˇ_x > 100  # standard layout has Tcˇ at far left
                if is_compact:
                    compact_seen = True
                # opacny_y intentionally ignored — parity determines direction.
                _ = opacny_y

                # Collect trip number columns: list of (x0, x1, text) tuples.
                trip_cols: List[Tuple[float, float, str]] = []
                for w in row:
                    if w is tcˇ_word:
                        continue
                    if w["text"].isdigit():
                        trip_cols.append((w["x0"], w["x1"], w["text"]))
                if not trip_cols and i + 1 < len(sorted_word_ys):
                    next_y = sorted_word_ys[i + 1]
                    next_row = sorted(word_rows[next_y], key=lambda w: w["x0"])
                    for w in next_row:
                        if w["text"].isdigit():
                            trip_cols.append((w["x0"], w["x1"], w["text"]))
                if not trip_cols:
                    i += 1
                    continue

                column_xs = [c[0] for c in trip_cols]
                column_ends = [c[1] for c in trip_cols]
                trip_numbers = [int(c[2]) for c in trip_cols]
                col_tol = column_tol(column_xs, default=12.0)
                column_boundaries = compute_column_boundaries(column_xs, column_ends)
                # Direction is determined by trip number parity — universal MHD BB
                # convention (odd → forward, even → return). Holds for both standard
                # and compact layouts.
                column_directions = [
                    "forward" if n % 2 == 1 else "return" for n in trip_numbers
                ]
                # Day-type accumulator per column
                services_per_col: List[set] = [set() for _ in trip_cols]

                # Determine plausible stop-label x range. In standard layout, stop number
                # is at x<25; in compact layout, it sits near Tcˇ.
                if is_compact:
                    stop_label_x_min = max(0, tcˇ_x - 30)
                    stop_label_x_max = tcˇ_x + 30
                else:
                    stop_label_x_min = 0
                    stop_label_x_max = 25

                def is_stop_row(rrow_inner) -> bool:
                    # Find the stop number word (digit, in stop label x range)
                    for w in rrow_inner:
                        if (
                            w["text"].isdigit()
                            and stop_label_x_min <= w["x0"] <= stop_label_x_max
                            and 1 <= int(w["text"]) <= 30
                        ):
                            # And there must be at least one alpha word right after it
                            stop_idx = w["x0"]
                            for w2 in rrow_inner:
                                if w2["x0"] > stop_idx and re.match(r"[A-Za-záéíóúýčďňšťžľĺŕäôÁÉÍÓÚÝČĎŇŠŤŽĽĹŔÄÔ]", w2["text"]):
                                    return True
                    return False

                # Walk rows below header until we hit a stop row
                j = i + 1
                while j < len(sorted_word_ys):
                    ry = sorted_word_ys[j]
                    rrow = sorted(word_rows[ry], key=lambda w: w["x0"])
                    if not rrow:
                        j += 1
                        continue
                    if is_stop_row(rrow):
                        break
                    # Code/marker row — assign symbols to columns
                    for w in rrow:
                        ci = assign_column(w["x0"], column_xs, tol=col_tol)
                        if ci is None:
                            continue
                        t = w["text"]
                        if t in SADZV_WEEKDAY_TOKENS:
                            services_per_col[ci].add(WEEKDAY)
                        elif t in SADZV_SATURDAY_TOKENS or t in SADZV_SUNDAY_TOKENS:
                            services_per_col[ci].add(WEEKEND)
                    j += 1

                # Compute service per column. A column might serve both weekday and weekend.
                # We'll add the times to BOTH lists if so.
                column_services: List[List[str]] = []
                for ci in range(len(trip_cols)):
                    s = services_per_col[ci]
                    if not s:
                        # Fallback: infer from trip number
                        s.add(WEEKDAY)
                    column_services.append(sorted(s))

                # Now walk stop-data rows
                while j < len(sorted_word_ys):
                    ry = sorted_word_ys[j]
                    rrow = sorted(word_rows[ry], key=lambda w: w["x0"])
                    if not rrow:
                        j += 1
                        continue
                    rft = rrow[0]["text"]
                    # New Tcˇ header → break
                    if any(w["text"].startswith("Tc") or w["text"] == "Tč" for w in rrow):
                        break
                    if rft.startswith(("opa", "pokra", "Predklad", "Schval", "isybus")):
                        j += 1
                        continue
                    if not is_stop_row(rrow):
                        j += 1
                        continue

                    # Find the stop-number word
                    stop_num_word = None
                    for w in rrow:
                        if (
                            w["text"].isdigit()
                            and stop_label_x_min <= w["x0"] <= stop_label_x_max
                            and 1 <= int(w["text"]) <= 30
                        ):
                            stop_num_word = w
                            break
                    if not stop_num_word:
                        j += 1
                        continue
                    stop_num_x = stop_num_word["x0"]

                    # Stop name: alpha-starting words after the stop number, until they leave the
                    # name region. The region width depends on layout: standard ~150px, compact ~80px.
                    name_region_end = stop_num_x + (90 if is_compact else 180)
                    name_parts: List[str] = []
                    for w in rrow:
                        if w is stop_num_word:
                            continue
                        if w["x0"] <= stop_num_x:
                            continue
                        if w["x0"] >= name_region_end:
                            break
                        t = w["text"]
                        if t.startswith("."):
                            continue
                        if t in STOP_MARKER_TOKENS or t in ("(cid:3)", "WC"):
                            continue
                        # Reject pure-numeric tokens (footer dates etc.)
                        if not re.search(r"[A-Za-záéíóúýčďňšťžľĺŕäôÁÉÍÓÚÝČĎŇŠŤŽĽĹŔÄÔ]", t):
                            continue
                        # Common ligature fixes
                        t = (
                            t.replace("cˇ", "č")
                            .replace("Cˇ", "Č")
                            .replace("dˇ", "ď")
                            .replace("Dˇ", "Ď")
                            .replace("nˇ", "ň")
                            .replace("Nˇ", "Ň")
                            .replace("tˇ", "ť")
                            .replace("Tˇ", "Ť")
                            .replace("l’", "ľ")
                            .replace("L’", "Ľ")
                        )
                        name_parts.append(t)
                    stop_name = " ".join(name_parts).strip()

                    # Get chars within ±5 of this stop row's y baseline.
                    relevant_chars = [c for c in chars if abs(c["top"] - ry) <= 5]
                    cell_chars: Dict[int, List[dict]] = defaultdict(list)
                    for c in relevant_chars:
                        # Exclude chars in the stop-name region
                        if not is_compact and c["x0"] < column_xs[0] - 25:
                            continue
                        if is_compact and stop_num_x - 5 < c["x0"] < name_region_end:
                            continue
                        # Don't bin chars that are clearly outside any column
                        # (more than 1 column-width before the first trip number).
                        if c["x0"] < column_xs[0] - 20:
                            continue
                        ci = assign_column_by_boundaries(
                            c["x0"], column_boundaries, len(column_xs)
                        )
                        if ci is not None:
                            cell_chars[ci].append(c)

                    # Build raw text per column
                    raw_per_col: List[str] = []
                    for ci in range(len(column_xs)):
                        cs = sorted(cell_chars.get(ci, []), key=lambda c: (round(c["top"]), c["x0"]))
                        raw = "".join(c["text"] for c in cs)
                        raw_per_col.append(raw)

                    # Convert raw cells to times. SADZV trick: when a column has only 2
                    # digits (minute only), reuse the hour from the previous column WITHIN
                    # the same direction.
                    times: List[Optional[str]] = [None] * len(column_xs)

                    def parse_dir_columns(indices: List[int]):
                        current_hour: Optional[int] = None
                        for ci in indices:
                            raw = raw_per_col[ci]
                            if "Æ" in raw:
                                continue
                            digits = re.sub(r"\D", "", raw)
                            if len(digits) >= 4:
                                t = normalise_time(digits[-4:])
                                if t:
                                    current_hour = int(t.split(":")[0])
                                    times[ci] = t
                            elif len(digits) == 3:
                                t = normalise_time(digits)
                                if t:
                                    current_hour = int(t.split(":")[0])
                                    times[ci] = t
                            elif len(digits) == 2 and current_hour is not None:
                                mm = int(digits)
                                if 0 <= mm <= 59:
                                    times[ci] = f"{current_hour:02d}:{mm:02d}"

                    fwd_indices = [ci for ci, d in enumerate(column_directions) if d == "forward"]
                    ret_indices = [ci for ci, d in enumerate(column_directions) if d == "return"]
                    parse_dir_columns(fwd_indices)
                    parse_dir_columns(ret_indices)

                    if stop_name:
                        for ci, t in enumerate(times):
                            if t is None:
                                continue
                            target = forward if column_directions[ci] == "forward" else return_
                            order = forward_order if column_directions[ci] == "forward" else return_order
                            if stop_name not in target:
                                target[stop_name] = {WEEKDAY: [], WEEKEND: []}
                                order.append(stop_name)
                            for svc in column_services[ci]:
                                target[stop_name][svc].append(t)

                    j += 1

                i = j

    # In compact layout, stop rows are listed in forward order; return direction visits
    # them in reverse, so reverse return_order.
    if compact_seen:
        return_order = list(reversed(return_order))

    def build_direction(target, order):
        if not order:
            return None
        # Filter stops with no times in either bucket
        nonempty = [
            s for s in order
            if target[s][WEEKDAY] or target[s][WEEKEND]
        ]
        if not nonempty:
            return None
        return {
            "headsign": nonempty[-1],
            "stops": [
                {
                    "name": s,
                    "times": {
                        WEEKDAY: sorted(set(target[s][WEEKDAY])),
                        WEEKEND: sorted(set(target[s][WEEKEND])),
                    },
                }
                for s in nonempty
            ],
        }

    directions = []
    fwd = build_direction(forward, forward_order)
    if fwd:
        directions.append(fwd)
    ret = build_direction(return_, return_order)
    if ret:
        directions.append(ret)

    return {
        "line": line_no,
        "name": name,
        "operator": "SADZV",
        "validFrom": valid_from,
        "directions": directions,
    }


# ---- format detection + entry ----------------------------------------------


def detect_format(pdf_path: Path) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        text = pdf.pages[0].extract_text() or ""
    if "DPM BB" in text or "Dopravný podnik mesta Banská Bystrica" in text:
        return "DPMBB"
    if "Slovenská autobusová doprava" in text or "Zvolen" in text:
        return "SADZV"
    return "UNKNOWN"


if __name__ == "__main__":
    pdf_path = Path(sys.argv[1])
    fmt = detect_format(pdf_path)
    if fmt == "DPMBB":
        out = parse_dpmbb(pdf_path)
    elif fmt == "SADZV":
        out = parse_sadzv(pdf_path)
    else:
        print(f"Unsupported format: {fmt}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(out, ensure_ascii=False, indent=2))
