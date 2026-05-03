#!/usr/bin/env python3
"""Download all DPMBB PDF timetables listed in lines.json into ./pdfs/."""
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import requests

ROOT = Path(__file__).parent
LINES = json.loads((ROOT / "lines.json").read_text())
OUT = ROOT / "pdfs"
OUT.mkdir(exist_ok=True)


def fetch(line):
    target = OUT / f"linka_{line['line']}.pdf"
    r = requests.get(line["url"], timeout=30)
    r.raise_for_status()
    target.write_bytes(r.content)
    return f"{line['line']}: {len(r.content) // 1024} KB"


with ThreadPoolExecutor(max_workers=8) as pool:
    for result in pool.map(fetch, LINES):
        print(result)
