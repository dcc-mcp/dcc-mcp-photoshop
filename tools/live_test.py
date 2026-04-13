#!/usr/bin/env python3
"""Live end-to-end test — runs in the SAME process as the MCP server.

Usage:
    python tools/live_test.py

This script starts the server, waits for the UXP plugin to connect,
then runs through all Photoshop capabilities including:
  - getDocumentInfo / listDocuments
  - listLayers (all + visible only)
  - createLayer / renameLayer / setLayerOpacity / setLayerVisibility
  - duplicateLayer / deleteLayer
  - executeScript
  - exportDocument (PNG + JPG)
  - saveDocument
"""

from __future__ import annotations

import json
import os
import sys
import time
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

passed = failed = 0


def ok(msg: str):
    global passed
    passed += 1
    print(f"  {GREEN}✓{RESET} {msg}")


def fail(msg: str):
    global failed
    failed += 1
    print(f"  {RED}✗{RESET} {msg}")


def section(title: str):
    print(f"\n{BOLD}── {title} ──{RESET}")


def call(bridge, method: str, **params):
    return bridge.call(method, **params)


def main():
    import dcc_mcp_photoshop
    from dcc_mcp_photoshop.bridge import PhotoshopBridge, BridgeRpcError

    # ── 1. Start server ───────────────────────────────────────────────────────
    section("1. Server startup")
    handle = dcc_mcp_photoshop.start_server(port=8765, ws_port=9001)
    ok(f"MCP HTTP: {handle.mcp_url()}")
    ok(f"WS bridge: ws://localhost:9001")

    # ── 2. Wait for UXP ───────────────────────────────────────────────────────
    section("2. Waiting for UXP plugin")
    from dcc_mcp_photoshop.api import is_photoshop_available, get_bridge
    print("  Open the dcc-mcp Bridge panel in Photoshop...")
    for i in range(60):
        if is_photoshop_available():
            ok(f"UXP connected after {i * 2}s")
            break
        print(f"  \r  [{i*2}s] waiting...", end="", flush=True)
        time.sleep(2)
    else:
        fail("UXP plugin did not connect within 120s")
        dcc_mcp_photoshop.stop_server()
        sys.exit(1)

    bridge = get_bridge()

    # ── 3. Document info ──────────────────────────────────────────────────────
    section("3. Document info")
    try:
        info = call(bridge, "ps.getDocumentInfo")
        ok(f"Name: {info.get('name')}")
        ok(f"Size: {info.get('width')} × {info.get('height')} px")
        ok(f"Resolution: {info.get('resolution')} dpi")
        ok(f"Color mode: {info.get('color_mode')}  Bit depth: {info.get('bit_depth')}")
        ok(f"Path: {info.get('path') or '(unsaved)'}")
        doc_name = info.get("name", "Untitled")
    except BridgeRpcError as e:
        fail(f"getDocumentInfo: {e} (code {e.code})")
        doc_name = "Untitled"
    except Exception as e:
        fail(f"getDocumentInfo: {e}")
        doc_name = "Untitled"

    # ── 4. List documents ─────────────────────────────────────────────────────
    section("4. List all documents")
    try:
        docs = call(bridge, "ps.listDocuments")
        ok(f"Open documents: {len(docs)}")
        for d in docs:
            print(f"    • {d.get('name')} ({d.get('width')}×{d.get('height')})")
    except Exception as e:
        fail(f"listDocuments: {e}")

    # ── 5. List layers ────────────────────────────────────────────────────────
    section("5. List layers")
    layers_before = []
    try:
        layers = call(bridge, "ps.listLayers", include_hidden=True)
        layers_before = layers
        ok(f"Total layers (inc. hidden): {len(layers)}")
        for l in layers:
            vis = "👁" if l.get("visible") else "🚫"
            print(f"    {vis} [{l.get('type','?'):12s}] {l.get('name','?')}  opacity={l.get('opacity')}%")
    except Exception as e:
        fail(f"listLayers: {e}")

    try:
        visible_layers = call(bridge, "ps.listLayers", include_hidden=False)
        ok(f"Visible layers only: {len(visible_layers)}")
    except Exception as e:
        fail(f"listLayers (visible only): {e}")

    # ── 6. Create layer ───────────────────────────────────────────────────────
    section("6. Create layer")
    new_layer_name = "dcc-mcp-test-layer"
    try:
        result = call(bridge, "ps.createLayer", name=new_layer_name, type="pixel")
        ok(f"Created pixel layer: '{result.get('name')}' (id={result.get('id')})")
    except Exception as e:
        fail(f"createLayer: {e}")

    # ── 7. Rename layer ───────────────────────────────────────────────────────
    section("7. Rename layer")
    renamed = "dcc-mcp-renamed"
    try:
        result = call(bridge, "ps.renameLayer", name=new_layer_name, new_name=renamed)
        ok(f"Renamed: '{result.get('old_name')}' → '{result.get('name')}'")
    except Exception as e:
        fail(f"renameLayer: {e}")

    # ── 8. Set layer opacity ──────────────────────────────────────────────────
    section("8. Set layer opacity")
    try:
        result = call(bridge, "ps.setLayerOpacity", name=renamed, opacity=42)
        ok(f"Opacity set to: {result.get('opacity')}%")
    except Exception as e:
        fail(f"setLayerOpacity: {e}")

    # ── 9. Set layer visibility ───────────────────────────────────────────────
    section("9. Set layer visibility")
    try:
        result = call(bridge, "ps.setLayerVisibility", name=renamed, visible=False)
        ok(f"Layer hidden: visible={result.get('visible')}")
        result = call(bridge, "ps.setLayerVisibility", name=renamed, visible=True)
        ok(f"Layer shown: visible={result.get('visible')}")
    except Exception as e:
        fail(f"setLayerVisibility: {e}")

    # ── 10. Duplicate layer ───────────────────────────────────────────────────
    section("10. Duplicate layer")
    dup_name = "dcc-mcp-duplicate"
    try:
        result = call(bridge, "ps.duplicateLayer", name=renamed, new_name=dup_name)
        ok(f"Duplicated: '{result.get('name')}' (id={result.get('id')})")
    except Exception as e:
        fail(f"duplicateLayer: {e}")

    # ── 11. Execute script (built-in safe expressions) ───────────────────────
    section("11. Execute script (safe built-in expressions)")
    for expr, label in [
        ("app.documents.length",           "文档数量"),
        ("app.activeDocument.name",        "文档名称"),
        ("app.activeDocument.layers.length","图层数量"),
        ("app.activeDocument.width",       "文档宽度"),
        ("app.activeDocument.height",      "文档高度"),
    ]:
        try:
            val = call(bridge, "ps.executeScript", code=expr)
            ok(f"{label}: {expr} = {val}")
        except Exception as e:
            fail(f"executeScript ({expr}): {e}")

    # ── 12. Export document ───────────────────────────────────────────────────
    section("12. Export document")
    # Use Windows Desktop path which PS can write to via localFileSystem
    desktop = os.path.expanduser("~/Desktop").replace("\\", "/")
    safe_doc = doc_name.replace(".psd", "").replace(".psb", "").replace(" ", "_")

    for fmt in ("png", "jpg"):
        out_path = f"{desktop}/dcc-mcp-test-{safe_doc}.{fmt}"
        try:
            result = call(bridge, "ps.exportDocument",
                          path=out_path, format=fmt, quality=90)
            if result.get("exported"):
                ok(f"Exported {fmt.upper()}: {result.get('path', out_path)}")
            else:
                fail(f"exportDocument ({fmt}): {result}")
        except BridgeRpcError as e:
            fail(f"exportDocument ({fmt}): {e} (code {e.code})")
        except Exception as e:
            fail(f"exportDocument ({fmt}): {e}")

    # ── 13. Save document ─────────────────────────────────────────────────────
    section("13. Save document")
    try:
        result = call(bridge, "ps.saveDocument")
        ok(f"Saved: {result}")
    except BridgeRpcError as e:
        # Expected if document has never been saved (no path)
        if e.code == -32001 or "path" in str(e).lower():
            ok(f"Save skipped (new unsaved document — expected): {e}")
        else:
            fail(f"saveDocument: {e} (code {e.code})")
    except Exception as e:
        fail(f"saveDocument: {e}")

    # ── 14. Delete test layers ────────────────────────────────────────────────
    section("14. Cleanup — delete test layers")
    for lname in (renamed, dup_name):
        try:
            result = call(bridge, "ps.deleteLayer", name=lname)
            ok(f"Deleted layer: '{result.get('name')}'")
        except BridgeRpcError as e:
            if e.code == -32001:
                ok(f"Layer '{lname}' already gone (ok)")
            else:
                fail(f"deleteLayer '{lname}': {e}")
        except Exception as e:
            fail(f"deleteLayer '{lname}': {e}")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'─'*50}")
    total = passed + failed
    if failed == 0:
        print(f"{GREEN}{BOLD}All {passed}/{total} tests passed!{RESET}")
    else:
        print(f"{YELLOW}{BOLD}{passed}/{total} passed, {failed} failed.{RESET}")

    dcc_mcp_photoshop.stop_server()


if __name__ == "__main__":
    main()
