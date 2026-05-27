#!/usr/bin/env python3
"""Download and update bank logos in logos/<bankcode>.png.

Source logos come from OPay's bundled nigerian_bankinfo.json (keyed by card BIN +
bank name). The CDN here is keyed by NIBSS bank code (banks.json), so each OPay
bank is matched to a code by normalized name, then its logo is saved as
logos/<code>.png. Unmatched banks are reported, not guessed.
"""
import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BANKS_JSON = ROOT / "banks.json"
LOGOS_DIR = ROOT / "logos"
DEFAULT_SOURCE = ROOT / "sources" / "opay_nigerian_bankinfo.json"
UA = "Mozilla/5.0 (bank-image-cdn updater)"

_STOP = {"plc", "bank", "nigeria", "nig", "limited", "ltd", "company", "co", "the"}

# OPay names that map to a banks.json code under a different name. Kept explicit
# so matches are auditable rather than fuzzy-guessed.
_ALIASES = {
    "guaranty trust": "000013",   # GTBANK PLC
    "union of": "000018",         # UNION BANK
    "aso savings and loans": "090001",
    "hasal": "090121",            # HASAL MICROFINANCE BANK
    "accion mfb": "090134",       # ACCION MICROFINANCE BANK
}


def normalize(name: str) -> str:
    words = re.sub(r"[^a-z0-9 ]", " ", name.lower()).split()
    return " ".join(w for w in words if w not in _STOP)


def load_code_index() -> dict[str, str]:
    index: dict[str, str] = {}
    for entry in json.loads(BANKS_JSON.read_text()):
        key = normalize(entry["name"])
        index.setdefault(key, entry["code"])
    return index


def load_sources(path: Path) -> dict[str, str]:
    """Distinct bank name -> logo url (large preferred)."""
    logos: dict[str, str] = {}
    for entry in json.loads(path.read_text()):
        url = entry.get("largeLogo") or entry.get("smallLogo")
        if entry.get("name") and url:
            logos.setdefault(entry["name"], url)
    return logos


def download(url: str, dest: Path) -> int:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    dest.write_bytes(data)
    return len(data)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    ap.add_argument("--dry-run", action="store_true", help="match only, no download")
    args = ap.parse_args()

    codes = load_code_index()
    sources = load_sources(args.source)
    LOGOS_DIR.mkdir(exist_ok=True)

    updated, unmatched, failed = [], [], []
    for name, url in sorted(sources.items()):
        norm = normalize(name)
        code = codes.get(norm) or _ALIASES.get(norm)
        if not code:
            unmatched.append(name)
            continue
        dest = LOGOS_DIR / f"{code}.png"
        if args.dry_run:
            updated.append((name, code, "would update"))
            continue
        try:
            size = download(url, dest)
            updated.append((name, code, f"{size} B"))
        except Exception as exc:  # noqa: BLE001
            failed.append((name, url, str(exc)))

    for name, code, note in updated:
        print(f"  ok   {code}.png  <- {name} ({note})")
    for name in unmatched:
        print(f"  skip no code for: {name}", file=sys.stderr)
    for name, url, err in failed:
        print(f"  FAIL {name}: {err}", file=sys.stderr)

    print(
        f"\n{len(updated)} updated, {len(unmatched)} unmatched, {len(failed)} failed "
        f"({len(sources)} source banks)"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
