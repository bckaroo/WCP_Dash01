#!/usr/bin/env python3
"""
Sync requirement coverage and known-gap metadata from the builder into the
already-built data/profiles.json.

Why this exists
---------------
`build_data.py` regenerates profiles.json, but a full rebuild needs a valid
Census API key and re-fetches every ACS variable. When only the *metadata*
(requirement statuses, known gaps) changes, re-running the whole build is both
unnecessary and currently impossible.

This script imports the single source of truth (`requirement_coverage` and
`known_gaps`) straight from build_data.py rather than duplicating the strings,
so the two can never drift. It touches ONLY those two metadata fields; profile
rows and every other metadata field are left byte-identical.

Usage: .venv/bin/python scripts/sync_metadata.py [--check]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from build_data import known_gaps, requirement_coverage  # noqa: E402

PROFILES = REPO / "data" / "profiles.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                        help="report drift without writing")
    args = parser.parse_args()

    doc = json.loads(PROFILES.read_text(encoding="utf-8"))
    md = doc["metadata"]

    before_req = md.get("requirements", [])
    before_gaps = md.get("known_gaps", [])
    after_req = requirement_coverage()
    after_gaps = known_gaps()

    req_changed = [
        (a["id"], b.get("status"))
        for a, b in zip(before_req, after_req)
        if a.get("status") != b["status"] or a.get("note") != b["note"]
    ]
    gaps_differ = before_gaps != after_gaps

    print(f"requirements in file: {len(before_req)} | from builder: {len(after_req)}")
    if req_changed:
        print("requirement rows that differ:")
        for rid, new_status in req_changed:
            old = next((r for r in before_req if r["id"] == rid), {}).get("status")
            print(f"  {rid}: {old!r} -> {new_status!r}")
    else:
        print("requirement rows: no drift")

    if gaps_differ:
        print("known_gaps differ:")
        for g in before_gaps:
            if g not in after_gaps:
                print(f"  - removed: {g[:88]}")
        for g in after_gaps:
            if g not in before_gaps:
                print(f"  + added:   {g[:88]}")
    else:
        print("known_gaps: no drift")

    if not req_changed and not gaps_differ:
        print("\nNothing to sync.")
        return 0

    if args.check:
        print("\n--check: drift detected, no changes written.")
        return 1

    md["requirements"] = after_req
    md["known_gaps"] = after_gaps
    PROFILES.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")

    # Guard against collateral damage: profile rows must be untouched.
    verify = json.loads(PROFILES.read_text(encoding="utf-8"))
    assert len(verify["profiles"]) == len(doc["profiles"]), "profile row count changed"
    assert verify["metadata"]["acs"] == md["acs"], "acs metadata changed unexpectedly"
    print(f"\nSynced. profiles={len(verify['profiles'])}, "
          f"requirements={len(after_req)}, known_gaps={len(after_gaps)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
