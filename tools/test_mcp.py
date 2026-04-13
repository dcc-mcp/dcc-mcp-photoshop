#!/usr/bin/env python3
"""End-to-end MCP capability test for dcc-mcp-photoshop.

Tests the full MCP protocol stack:
  1. initialize
  2. tools/list  (discover registered tools)
  3. load_skill  (load photoshop-document skill)
  4. photoshop_document__get_document_info  (requires UXP connected)
  5. photoshop_document__list_layers        (requires UXP connected)

Usage:
    python tools/test_mcp.py
    python tools/test_mcp.py --skip-ps   # skip tools that need Photoshop
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from typing import Any

MCP_URL = "http://127.0.0.1:8765/mcp"
GREEN = "\033[32m"
RED   = "\033[31m"
YELLOW = "\033[33m"
BOLD  = "\033[1m"
RESET = "\033[0m"

_session_id: str | None = None


def _rpc(method: str, params: dict | None = None, use_session: bool = True) -> dict:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params:
        payload["params"] = params

    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if use_session and _session_id:
        headers["Mcp-Session-Id"] = _session_id

    req = urllib.request.Request(
        MCP_URL,
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode()
            # Handle SSE format: "data: {...}\n\n"
            if raw.startswith("data:"):
                raw = raw.split("data:", 1)[1].strip()
            return json.loads(raw)
    except Exception as exc:
        return {"error": {"message": str(exc)}}


def ok(msg: str) -> None:
    print(f"  {GREEN}✓{RESET} {msg}")


def fail(msg: str) -> None:
    print(f"  {RED}✗{RESET} {msg}")


def skip(msg: str) -> None:
    print(f"  {YELLOW}⊘{RESET} {msg}")


def section(title: str) -> None:
    print(f"\n{BOLD}── {title} ──{RESET}")


def run_tests(skip_ps: bool) -> int:
    global _session_id
    errors = 0

    # ── 1. initialize ────────────────────────────────────────────────────
    section("1. MCP initialize")
    resp = _rpc("initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "mcp-test", "version": "1.0"},
    }, use_session=False)

    if "error" in resp:
        fail(f"initialize failed: {resp['error']}")
        errors += 1
        return errors

    result = resp.get("result", {})
    _session_id = result.get("__session_id")
    server_info = result.get("serverInfo", {})
    protocol = result.get("protocolVersion", "?")

    ok(f"Server: {server_info.get('name')} v{server_info.get('version')}")
    ok(f"Protocol: {protocol}")
    ok(f"Session ID: {_session_id[:16]}..." if _session_id else "No session")

    caps = result.get("capabilities", {})
    if caps.get("tools"):
        ok(f"Tools capability: {caps['tools']}")
    else:
        fail("No tools capability reported")
        errors += 1

    # ── 2. tools/list (before skill load) ────────────────────────────────
    section("2. tools/list (initial)")
    resp = _rpc("tools/list")
    if "error" in resp:
        fail(f"tools/list failed: {resp['error']}")
        errors += 1
    else:
        tools = resp.get("result", {}).get("tools", [])
        ok(f"Found {len(tools)} tool(s) before skill load")
        for t in tools[:10]:
            name = t.get("name", "?")
            desc = t.get("description", "")[:60]
            print(f"    • {name}: {desc}")
        if len(tools) > 10:
            print(f"    ... and {len(tools) - 10} more")

    # ── 3. find_skills ───────────────────────────────────────────────────
    section("3. find_skills")
    resp = _rpc("tools/call", {
        "name": "find_skills",
        "arguments": {"query": "photoshop"},
    })
    if "error" in resp:
        fail(f"find_skills error: {resp['error']}")
        errors += 1
    else:
        content = resp.get("result", {}).get("content", [])
        text = content[0].get("text", "") if content else ""
        ok(f"find_skills response: {text[:120]}")

    # ── 4. load_skill ────────────────────────────────────────────────────
    section("4. load_skill(photoshop-document)")
    resp = _rpc("tools/call", {
        "name": "load_skill",
        "arguments": {"skill_name": "photoshop-document"},
    })
    if "error" in resp:
        fail(f"load_skill error: {resp['error']}")
        errors += 1
    else:
        content = resp.get("result", {}).get("content", [])
        text = content[0].get("text", "") if content else ""
        ok(f"load_skill: {text[:120]}")

    # ── 5. tools/list (after skill load) ─────────────────────────────────
    section("5. tools/list (after skill load)")
    resp = _rpc("tools/list")
    if "error" in resp:
        fail(f"tools/list failed: {resp['error']}")
        errors += 1
    else:
        tools = resp.get("result", {}).get("tools", [])
        ok(f"Found {len(tools)} tool(s) after skill load")
        ps_tools = [t for t in tools if "photoshop_document" in t.get("name", "")]
        if ps_tools:
            ok(f"Photoshop tools registered: {[t['name'] for t in ps_tools]}")
        else:
            fail("No photoshop_document tools found after load_skill")
            errors += 1
        for t in tools:
            name = t.get("name", "?")
            schema = t.get("inputSchema", {})
            props = list(schema.get("properties", {}).keys())
            print(f"    • {name}" + (f"  params={props}" if props else "  (no params)"))

    # ── 6. get_document_info ──────────────────────────────────────────────
    section("6. photoshop_document__get_document_info")
    if skip_ps:
        skip("Skipped (--skip-ps)")
    else:
        resp = _rpc("tools/call", {
            "name": "photoshop_document__get_document_info",
            "arguments": {},
        })
        if "error" in resp:
            fail(f"RPC error: {resp['error']}")
            errors += 1
        else:
            content = resp.get("result", {}).get("content", [])
            text = content[0].get("text", "") if content else ""
            try:
                data = json.loads(text)
                if data.get("success"):
                    ctx = data.get("context", {})
                    ok(f"Document: {ctx.get('document_name')}  {ctx.get('width')}×{ctx.get('height')}px  {ctx.get('resolution')}dpi")
                    ok(f"Color mode: {ctx.get('color_mode')}  Bit depth: {ctx.get('bit_depth')}")
                else:
                    fail(f"Tool returned error: {data.get('message')} | {data.get('error','')[:100]}")
                    errors += 1
            except Exception:
                ok(f"Response: {text[:200]}")

    # ── 7. list_layers ────────────────────────────────────────────────────
    section("7. photoshop_document__list_layers")
    if skip_ps:
        skip("Skipped (--skip-ps)")
    else:
        resp = _rpc("tools/call", {
            "name": "photoshop_document__list_layers",
            "arguments": {"include_hidden": True},
        })
        if "error" in resp:
            fail(f"RPC error: {resp['error']}")
            errors += 1
        else:
            content = resp.get("result", {}).get("content", [])
            text = content[0].get("text", "") if content else ""
            try:
                data = json.loads(text)
                if data.get("success"):
                    ctx = data.get("context", {})
                    count = ctx.get("count", 0)
                    layers = ctx.get("layers", [])
                    ok(f"Found {count} layer(s): {layers}")
                else:
                    fail(f"Tool returned error: {data.get('message')} | {data.get('error','')[:100]}")
                    errors += 1
            except Exception:
                ok(f"Response: {text[:200]}")

    # ── 8. list_skills ────────────────────────────────────────────────────
    section("8. list_skills")
    resp = _rpc("tools/call", {
        "name": "list_skills",
        "arguments": {},
    })
    if "error" in resp:
        skip(f"list_skills not available: {resp['error'].get('message','')[:60]}")
    else:
        content = resp.get("result", {}).get("content", [])
        text = content[0].get("text", "") if content else ""
        ok(f"list_skills: {text[:200]}")

    # ── Summary ───────────────────────────────────────────────────────────
    section("Summary")
    if errors == 0:
        print(f"\n{GREEN}{BOLD}All tests passed!{RESET}")
    else:
        print(f"\n{RED}{BOLD}{errors} test(s) failed.{RESET}")

    return errors


def main() -> None:
    global MCP_URL
    parser = argparse.ArgumentParser(description="MCP capability test for dcc-mcp-photoshop")
    parser.add_argument("--skip-ps", action="store_true",
                        help="Skip tools that require Photoshop to be open")
    parser.add_argument("--url", default=MCP_URL, help=f"MCP server URL (default: {MCP_URL})")
    args = parser.parse_args()

    MCP_URL = args.url

    print(f"{BOLD}dcc-mcp-photoshop MCP Capability Test{RESET}")
    print(f"Endpoint: {MCP_URL}")
    if args.skip_ps:
        print(f"{YELLOW}Note: Photoshop-dependent tests will be skipped{RESET}")
    else:
        print(f"{YELLOW}Note: Tests 6-7 require Photoshop open with dcc-mcp Bridge panel connected{RESET}")

    errors = run_tests(skip_ps=args.skip_ps)
    sys.exit(0 if errors == 0 else 1)


if __name__ == "__main__":
    main()
