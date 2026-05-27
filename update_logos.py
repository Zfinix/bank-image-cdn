#!/usr/bin/env python3
"""Update logos/<code>.png from OPay's bank_logo icon endpoint.

OPay serves a transfer-bank icon per NIBSS bank code at
  https://files.opayweb.com/images/api/icon/bank_logo/<code>.png
which is the same code scheme as banks.json and the logos/<code>.png naming
here, so each bank maps 1:1 by code with no name matching. Codes OPay has no
icon for are reported and left untouched.
"""
import argparse
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BANKS_JSON = ROOT / "banks.json"
LOGOS_DIR = ROOT / "logos"
BASE = "https://files.opayweb.com/images/api/icon/bank_logo/"
UA = "Mozilla/5.0 (bank-image-cdn updater)"


def fetch(code: str, dry_run: bool) -> tuple[str, str]:
    url = f"{BASE}{code}.png"
    method = "HEAD" if dry_run else "GET"
    req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = b"" if dry_run else resp.read()
    except Exception as exc:  # noqa: BLE001
        return code, f"miss ({getattr(exc, 'code', 'err')})"
    if not dry_run:
        (LOGOS_DIR / f"{code}.png").write_bytes(data)
        return code, f"ok ({len(data)} B)"
    return code, "available"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="probe only, no writes")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    LOGOS_DIR.mkdir(exist_ok=True)
    codes = [e["code"] for e in json.loads(BANKS_JSON.read_text())]

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda c: fetch(c, args.dry_run), codes))

    hits = [c for c, note in results if note.startswith(("ok", "available"))]
    misses = [c for c, note in results if note.startswith("miss")]
    for code, note in results:
        if not note.startswith("miss"):
            print(f"  {code}: {note}")
    verb = "available" if args.dry_run else "written"
    print(f"\n{len(hits)} {verb}, {len(misses)} missing ({len(codes)} codes checked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
