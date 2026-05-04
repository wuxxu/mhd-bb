#!/usr/bin/env python3
"""Parse all PDFs and generate JSON files for the frontend.

After regenerating from the PDF pipeline, picks up any manually-curated
JSON files in OUT_DIR (those carrying ``"manualEntry": true``) and merges
them into the index so the frontend can list them too. The PDF pipeline
itself never touches those files.
"""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from parse_pdf import parse_dpmbb, parse_sadzv, detect_format

ROOT = Path(__file__).parent
LINES = json.loads((ROOT / "lines.json").read_text())
PDF_DIR = ROOT / "pdfs"
# Output goes into the eventual frontend's public/data directory.
OUT_DIR = ROOT.parent / "web" / "public" / "data" / "lines"
OUT_DIR.mkdir(parents=True, exist_ok=True)
INDEX_PATH = OUT_DIR.parent / "lines.json"

index = []
errors = []
auto_lines = set()
for entry in LINES:
    line_no = entry["line"]
    pdf = PDF_DIR / f"linka_{line_no}.pdf"
    if not pdf.exists():
        errors.append((line_no, "missing PDF"))
        continue
    try:
        fmt = detect_format(pdf)
        if fmt == "DPMBB":
            data = parse_dpmbb(pdf)
        elif fmt == "SADZV":
            data = parse_sadzv(pdf)
        else:
            errors.append((line_no, f"unknown format {fmt}"))
            continue
    except Exception as e:
        errors.append((line_no, f"parse error: {e}"))
        continue

    out_path = OUT_DIR / f"{line_no}.json"
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    auto_lines.add(line_no)

    direction_summaries = [
        {
            "headsign": d["headsign"],
            "stopCount": len(d["stops"]),
        }
        for d in data["directions"]
    ]
    index.append({
        "line": line_no,
        "name": entry["name"],
        "fullName": data["name"],
        "operator": data["operator"],
        "validFrom": data["validFrom"],
        "directions": direction_summaries,
    })
    print(f"  ✓ linka {line_no}: {len(data['directions'])} dirs, "
          f"{sum(len(d['stops']) for d in data['directions'])} stops total")

# Pick up any manually-curated JSON files that aren't covered by the PDF pipeline
manual_count = 0
for json_path in sorted(OUT_DIR.glob("*.json")):
    line_no = json_path.stem
    if line_no in auto_lines:
        continue
    try:
        data = json.loads(json_path.read_text())
    except Exception as e:
        errors.append((line_no, f"manual JSON read error: {e}"))
        continue
    if not data.get("manualEntry"):
        # Not auto-parsed AND not flagged as manual — likely a stale leftover
        errors.append((line_no, "JSON exists but no PDF and no manualEntry flag"))
        continue
    direction_summaries = [
        {"headsign": d["headsign"], "stopCount": len(d["stops"])}
        for d in data["directions"]
    ]
    index.append({
        "line": line_no,
        "name": data.get("name", "")[:60],
        "fullName": data.get("name", ""),
        "operator": data.get("operator", "MANUAL"),
        "validFrom": data.get("validFrom", ""),
        "directions": direction_summaries,
        "manualEntry": True,
    })
    manual_count += 1
    print(f"  + linka {line_no} (manual): {len(data['directions'])} dirs")

# Sort index numerically by line number
index.sort(key=lambda x: int(x["line"]))
INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2))
print(f"\nWrote {len(index)} lines ({manual_count} manual). Index → {INDEX_PATH}")
if errors:
    print(f"\n{len(errors)} errors:")
    for ln, err in errors:
        print(f"  linka {ln}: {err}")
