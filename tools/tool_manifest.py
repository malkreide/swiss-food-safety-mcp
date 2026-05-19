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


def _manifest() -> dict:
    """Build the deterministic tool manifest with its SHA-256 digest."""
    tools = asyncio.run(mcp.list_tools())
    entries: dict[str, dict] = {}
    for tool in tools:
        mcp_tool = tool.to_mcp_tool()
        annotations = mcp_tool.annotations
        entries[mcp_tool.name] = {
            "description": mcp_tool.description or "",
            "input_schema": mcp_tool.inputSchema,
            "annotations": annotations.model_dump() if annotations else None,
        }
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
