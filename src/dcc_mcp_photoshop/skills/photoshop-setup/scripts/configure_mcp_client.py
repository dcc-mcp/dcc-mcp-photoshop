"""Configure MCP client to connect to the dcc-mcp gateway."""

from __future__ import annotations

import json
import os
import platform

from dcc_mcp_core.skill import skill_entry


def _find_claude_config_paths() -> list[str]:
    """Return possible Claude Desktop config paths for the current platform."""
    system = platform.system()
    if system == "Windows":
        appdata = os.environ.get("APPDATA", "")
        return [os.path.join(appdata, "Claude", "claude_desktop_config.json")]
    elif system == "Darwin":
        home = os.path.expanduser("~")
        return [os.path.join(home, "Library", "Application Support", "Claude", "claude_desktop_config.json")]
    else:
        home = os.path.expanduser("~")
        return [os.path.join(home, ".config", "Claude", "claude_desktop_config.json")]


def _find_vscode_config_paths() -> list[str]:
    """Return possible VS Code settings paths."""
    system = platform.system()
    if system == "Windows":
        appdata = os.environ.get("APPDATA", "")
        pfx = os.path.join(appdata, "Code")
    elif system == "Darwin":
        home = os.path.expanduser("~")
        pfx = os.path.join(home, "Library", "Application Support", "Code")
    else:
        home = os.path.expanduser("~")
        pfx = os.path.join(home, ".config", "Code")

    settings_files = []
    for variant in ["User", "User/globalStorage"]:
        p = os.path.join(pfx, variant, "settings.json")
        settings_files.append(p)
    return settings_files


def _configure_claude(gateway_url: str, server_name: str, overwrite: bool) -> dict:
    """Write or update claude_desktop_config.json."""
    config_paths = _find_claude_config_paths()
    config_path = None
    for p in config_paths:
        if os.path.isfile(p) or os.path.isdir(os.path.dirname(p)):
            config_path = p
            break

    if not config_path:
        return {
            "ok": False,
            "path": config_paths[0] if config_paths else "",
            "detail": "Claude Desktop config directory not found. Is Claude Desktop installed?",
            "guide": _claude_manual_guide(gateway_url, server_name),
        }

    config = {}
    if os.path.isfile(config_path) and not overwrite:
        try:
            with open(config_path) as f:
                config = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    if "mcpServers" not in config:
        config["mcpServers"] = {}

    config["mcpServers"][server_name] = {
        "url": gateway_url,
    }

    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")

    return {
        "ok": True,
        "path": config_path,
        "detail": f"Claude Desktop configured: {server_name} → {gateway_url}",
    }


def _configure_cursor(gateway_url: str, server_name: str) -> dict:
    """Generate Cursor MCP setup guide (Cursor needs manual UI input)."""
    guide = (
        f"# Cursor MCP Configuration\n"
        f"\n"
        f"1. Open Cursor → Settings (Ctrl+Comma / Cmd+Comma)\n"
        f"2. Go to Features → MCP Servers\n"
        f"3. Click 'Add New MCP Server'\n"
        f"\n"
        f"   Name: {server_name}\n"
        f"   Type: HTTP (SSE / Streamable HTTP)\n"
        f"   URL: {gateway_url}\n"
        f"\n"
        f"4. Click Save\n"
        f"5. Test by asking the AI to list tools\n"
    )
    return {
        "ok": False,
        "detail": "Cursor configuration must be done manually in the UI",
        "guide": guide,
    }


def _configure_vscode(gateway_url: str, server_name: str, overwrite: bool) -> dict:
    """Write or update VS Code MCP settings."""
    config_paths = _find_vscode_config_paths()
    config_path = None
    for p in config_paths:
        if os.path.isfile(p) or (
            os.path.dirname(p)
            and any(os.path.isdir(os.path.dirname(p).replace("globalStorage", x)) for x in ["globalStorage", "User"])
        ):
            config_path = p
            break

    if not config_path:
        return {
            "ok": False,
            "path": config_paths[0] if config_paths else "",
            "detail": "VS Code settings not found",
            "guide": _vscode_manual_guide(gateway_url, server_name),
        }

    config = {}
    if os.path.isfile(config_path) and not overwrite:
        try:
            with open(config_path) as f:
                config = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    if "mcp" not in config:
        config["mcp"] = {}
    if "servers" not in config["mcp"]:
        config["mcp"]["servers"] = {}

    config["mcp"]["servers"][server_name] = {
        "url": gateway_url,
    }

    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)
        f.write("\n")

    return {
        "ok": True,
        "path": config_path,
        "detail": f"VS Code configured: {server_name} → {gateway_url}",
    }


def _claude_manual_guide(gateway_url: str, server_name: str) -> str:
    """Generate manual Claude Desktop config instructions."""
    config = {
        "mcpServers": {
            server_name: {
                "url": gateway_url,
            }
        }
    }
    config_json = json.dumps(config, indent=2)

    paths = _find_claude_config_paths()
    return (
        f"# Claude Desktop Manual Configuration\n"
        f"\n"
        f"Create or edit: {paths[0] if paths else 'claude_desktop_config.json'}\n"
        f"\n"
        f"```json\n{config_json}\n```\n"
    )


def _vscode_manual_guide(gateway_url: str, server_name: str) -> str:
    """Generate manual VS Code config instructions."""
    config = {
        "mcp": {
            "servers": {
                server_name: {
                    "url": gateway_url,
                }
            }
        }
    }
    config_json = json.dumps(config, indent=4)

    return f"# VS Code Manual Configuration\n\nAdd to your VS Code `settings.json`:\n\n```json\n{config_json}\n```\n"


@skill_entry
def configure_mcp_client(
    client_type: str = "claude_desktop",
    server_name: str = "photoshop",
    gateway_url: str = "http://127.0.0.1:9765/mcp",
    overwrite: bool = False,
    **kwargs,
) -> dict:
    """Configure an MCP client to connect to the dcc-mcp gateway.

    Writes or generates configuration for Claude Desktop, Cursor, or VS Code
    so the AI assistant can talk to Photoshop through the dcc-mcp gateway.

    Args:
        client_type: Target client: "claude_desktop", "cursor", "vscode", or "all".
        server_name: Server name shown in the MCP client (default: "photoshop").
        gateway_url: Gateway MCP endpoint URL (default: http://127.0.0.1:9765/mcp).
        overwrite: Replace existing config instead of merging.

    Returns:
        dict: Configuration result per client.
    """
    valid_types = {"claude_desktop", "cursor", "vscode", "all"}
    if client_type not in valid_types:
        return {
            "success": False,
            "summary": f"Invalid client_type: {client_type}",
            "details": {},
            "prompt": f"Choose one of: {', '.join(sorted(valid_types))}",
        }

    results = {}

    if client_type in ("claude_desktop", "all"):
        results["claude_desktop"] = _configure_claude(gateway_url, server_name, overwrite)

    if client_type in ("cursor", "all"):
        results["cursor"] = _configure_cursor(gateway_url, server_name)

    if client_type in ("vscode", "all"):
        results["vscode"] = _configure_vscode(gateway_url, server_name, overwrite)

    configured = [k for k, v in results.items() if v.get("ok")]
    if configured:
        summary = f"MCP client(s) configured: {', '.join(configured)} → {gateway_url}"
    else:
        summary = "Configuration generated (manual steps required for some clients)"

    return {
        "success": len(configured) > 0 or client_type == "cursor",
        "summary": summary,
        "details": results,
        "prompt": (
            "Restart your MCP client (Claude Desktop / Cursor / VS Code) to pick up the new config. "
            "Use verify_connection to confirm the bridge is working, then use tools like "
            "photoshop-document/list_layers or photoshop-image/create_document."
        ),
    }


def main(**kwargs) -> dict:
    return configure_mcp_client(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
