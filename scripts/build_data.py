#!/usr/bin/env python3
"""Parse all PDFs and generate JSON files for the frontend."""
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

# Sort index numerically by line number
index.sort(key=lambda x: int(x["line"]))
INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2))
print(f"\nWrote {len(index)} lines. Index → {INDEX_PATH}")
if errors:
    print(f"\n{len(errors)} errors:")
    for ln, err in errors:
        print(f"  linka {ln}: {err}")
