#!/usr/bin/env python3
"""Tool-definition hash manifest (audit finding SEC-022).

Computes a SHA-256 over every exposed tool's name, description, input schema
and annotations. CI compares the result against the committed baseline so that
an unintended change to a tool definition ("rug pull") fails the build.

Usage:
    python tools/tool_manifest.py --check     # fail if tools differ from baseline
    python tools/tool_manifest.py --update    # rewrite the baseline (intentional change)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from pathlib import Path

from swiss_food_safety_mcp.server import mcp

BASELINE = Path(__file__).parent / "tool-hashes.json"


def _entries() -> dict[str, dict]:
    """Die gehashten Werkzeugeintraege — eigene Funktion, damit sie pruefbar ist.

    Solange dieser Aufbau in `_manifest` eingeschlossen war, kam von aussen nur
    der fertige Digest heraus. Ein Test konnte damit zwar merken, *dass* sich
    etwas geaendert hat, aber nicht, *womit* gehasht wurde — und genau das ist
    die Eigenschaft, an der der Waechter haengt.
    """
    entries: dict[str, dict] = {}
    for tool in asyncio.run(mcp.list_tools()):
        mcp_tool = tool.to_mcp_tool()
        annotations = mcp_tool.annotations
        entries[mcp_tool.name] = {
            "description": mcp_tool.description or "",
            "input_schema": mcp_tool.input_schema,
            "annotations": annotations.model_dump(by_alias=True) if annotations else None,
        }
    return entries


def _manifest() -> dict:
    """Build the deterministic tool manifest with its SHA-256 digest.

    `by_alias=True` is load-bearing, not styling. The digest must cover what a
    client receives over the wire, and that is the alias spelling — the spec
    serialises `readOnlyHint`, not `read_only_hint`. Dumping by field name
    instead ties a rug-pull detector to the SDK's *internal* Python naming, so
    it reports the one thing that cannot hurt anyone and stays silent on real
    drift underneath.

    That is not hypothetical. The `mcp` 1.x -> 2.x upgrade renamed every
    annotation field, and the bare `model_dump()` that stood here changed the
    digest from `da85755…` to `80cf836…` while not one tool definition had
    moved: dumping the same objects with `by_alias=True` reproduced the
    committed baseline byte for byte. Rebaselining on that signal would have
    re-pinned the detector against a cosmetic change — and waved through
    whatever else rode along in the same commit.
    """
    entries = _entries()
    blob = json.dumps(entries, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    return {"sha256": digest, "tools": sorted(entries)}


def main() -> int:
    manifest = _manifest()

    if "--update" in sys.argv:
        BASELINE.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(f"Baseline updated — sha256={manifest['sha256']}")
        return 0

    if not BASELINE.exists():
        print("No baseline found. Run: python tools/tool_manifest.py --update", file=sys.stderr)
        return 1

    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    if baseline.get("sha256") != manifest["sha256"]:
        print("Tool definitions changed versus the committed baseline.", file=sys.stderr)
        print(f"  baseline: {baseline.get('sha256')}", file=sys.stderr)
        print(f"  current:  {manifest['sha256']}", file=sys.stderr)
        print(
            "If intentional, run `python tools/tool_manifest.py --update` "
            "and record the change in CHANGELOG.md.",
            file=sys.stderr,
        )
        return 1

    print(f"Tool definitions match the baseline — sha256={manifest['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
