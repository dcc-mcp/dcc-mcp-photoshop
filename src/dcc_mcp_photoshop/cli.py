"""dcc-mcp-photoshop CLI — bridge plugin for use with dcc-mcp-server.exe.

This module is the entry point for:
- ``python -m dcc_mcp_photoshop``
- ``dcc-mcp-photoshop`` (pip entry-point)

Default mode (bridge-only)
---------------------------
Runs the WebSocket bridge + HTTP RPC server for use with dcc-mcp-server.exe::

    # Terminal 1: start MCP server (Rust binary, no Python needed)
    dcc-mcp-server.exe --dcc photoshop --mcp-port 8765 --skill-paths ./skills --no-bridge --gateway-port 9765 --registry-dir ~/.dcc-mcp/registry

    # Terminal 2: start bridge plugin (Python, connects to UXP)
    python -m dcc_mcp_photoshop

MCP clients connect to ``http://127.0.0.1:8765/mcp`` (direct, stable port)
or ``http://127.0.0.1:9765/mcp/dcc/photoshop`` (gateway proxy by DCC type).

Embedded mode
-------------
For development only — starts MCP server + bridge in one Python process::

    python -m dcc_mcp_photoshop --embedded

Requires Python on the server machine. Not suitable for deployment.
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import time

logger = logging.getLogger(__name__)


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    if not verbose:
        logging.getLogger("dcc_mcp_core").setLevel(logging.WARNING)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dcc-mcp-photoshop",
        description=(
            "DCC MCP Bridge Plugin for Adobe Photoshop\n\n"
            "Default: bridge-only (for use with dcc-mcp-server.exe)\n"
            "Embedded: MCP server + bridge in one process (dev only)"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples (bridge-only — default, for deployment):
  dcc-mcp-server.exe --dcc photoshop --mcp-port 8765 --skill-paths ./skills --no-bridge --gateway-port 9765 --registry-dir ~/.dcc-mcp/registry
  python -m dcc_mcp_photoshop

Examples (embedded — dev only, requires Python on server):
  python -m dcc_mcp_photoshop --embedded

Environment variables:
  DCC_MCP_REGISTRY_DIR            Shared FileRegistry directory (must match dcc-mcp-server.exe --registry-dir)
  DCC_MCP_PHOTOSHOP_SKILL_PATHS   Extra skill directories
  DCC_MCP_SKILL_PATHS             Global skill directories
""",
    )
    parser.add_argument(
        "--embedded", action="store_true",
        help="Embedded mode: MCP server + bridge in one Python process (dev only)",
    )
    parser.add_argument(
        "--mcp-port", type=int, default=8765,
        help="MCP HTTP server port (embedded mode; default: 8765)",
    )
    parser.add_argument(
        "--ws-port", type=int, default=9001,
        help="WebSocket bridge port for UXP plugin (default: 9001)",
    )
    parser.add_argument(
        "--ws-host", default="localhost",
        help="WebSocket bind host (default: localhost)",
    )
    parser.add_argument(
        "--rpc-port", type=int, default=9100,
        help="HTTP RPC server port for cross-process bridge access (default: 9100)",
    )
    parser.add_argument(
        "--gateway-port", type=int, default=None,
        help="Gateway competition port (embedded mode; default: env DCC_MCP_GATEWAY_PORT or 9765, 0=disable)",
    )
    parser.add_argument(
        "--server-name", default="photoshop-mcp",
        help="Server name reported in MCP (default: photoshop-mcp)",
    )
    parser.add_argument(
        "--skill-paths", nargs="*", default=[],
        metavar="PATH",
        help="Extra skill directories",
    )
    parser.add_argument(
        "--no-builtins", action="store_true",
        help="Do not discover built-in skills",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--version", action="version",
        version=f"%(prog)s {_get_version()}",
    )
    return parser


def _get_version() -> str:
    try:
        from dcc_mcp_photoshop.__version__ import __version__
        return __version__
    except Exception:
        return "0.0.0"


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _setup_logging(args.verbose)

    print(f"dcc-mcp-photoshop v{_get_version()}")
    print()

    import dcc_mcp_photoshop  # noqa: PLC0415

    # Handle Ctrl+C gracefully
    stop = [False]

    def _on_signal(*_):
        stop[0] = True

    signal.signal(signal.SIGINT, _on_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _on_signal)

    from dcc_mcp_photoshop.api import get_bridge, is_photoshop_available  # noqa: PLC0415

    def _update_scene(scene_name: str) -> None:
        """Update scene info in FileRegistry so gateway /instances shows it.

        Also writes to ~/.dcc-mcp/bridge-photoshop.json for skill script discovery.
        """
        # 1) Update FileRegistry (gateway /instances will show scene)
        try:
            from dcc_mcp_core import TransportManager  # noqa: PLC0415

            registry_dir = (
                os.environ.get("DCC_MCP_REGISTRY_DIR", "")
                or os.path.expanduser("~/.dcc-mcp/registry")
            )
            if os.path.isdir(registry_dir):
                mgr = TransportManager(registry_dir=registry_dir)
                instances = mgr.list_instances("photoshop")
                for inst in instances:
                    if inst.status.name.lower() not in ("shuttingdown", "unreachable"):
                        mgr.update_scene("photoshop", inst.instance_id, scene=scene_name)
                        break
        except Exception:
            pass  # Non-critical

        # 2) Update bridge config file (skill scripts read this for RPC endpoint)
        try:
            import json  # noqa: PLC0415
            config_path = os.path.expanduser("~/.dcc-mcp/bridge-photoshop.json")
            config = {}
            if os.path.isfile(config_path):
                with open(config_path) as f:
                    config = json.load(f)
            config["dcc_type"] = "photoshop"
            config["scene"] = scene_name
            # Keep existing bridge_url if present
            rpc_url = f"http://localhost:{args.rpc_port}/rpc"
            if "bridge_url" not in config or not config["bridge_url"]:
                config["bridge_url"] = rpc_url
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    if args.embedded:
        # Embedded mode (dev only) — MCP server + bridge in one Python process
        print("  [EMBEDDED MODE] MCP server + WebSocket bridge (dev only)")
        print(f"  MCP server  : http://{args.ws_host}:{args.mcp_port}/mcp")
        print(f"  WS bridge   : ws://{args.ws_host}:{args.ws_port}")
        print(f"  RPC endpoint: http://{args.ws_host}:{args.rpc_port}/rpc")
        print()
        print("Waiting for Photoshop UXP plugin to connect...")
        print("Press Ctrl+C to stop.\n")

        handle = dcc_mcp_photoshop.start_server(
            port=args.mcp_port,
            server_name=args.server_name,
            ws_host=args.ws_host,
            ws_port=args.ws_port,
            rpc_port=args.rpc_port,
            gateway_port=args.gateway_port,
            register_builtins=not args.no_builtins,
            extra_skill_paths=args.skill_paths or None,
        )

        mcp_url = handle.mcp_url() if hasattr(handle, "mcp_url") else str(handle)
        logger.info("MCP server started at %s", mcp_url)

        last_status = None
        last_scene = None
        try:
            while not stop[0]:
                connected = is_photoshop_available()
                status = "CONNECTED" if connected else "waiting for UXP plugin..."
                if status != last_status:
                    sym = "✓" if connected else "○"
                    print(f"\r[{sym}] {status}          ", end="", flush=True)
                    last_status = status

                if connected:
                    try:
                        bridge = get_bridge()
                        doc_info = bridge.call("ps.getDocumentInfo")
                        scene_name = doc_info.get("name") if isinstance(doc_info, dict) else None
                        if scene_name and scene_name != last_scene:
                            _update_scene(scene_name)
                            last_scene = scene_name
                            print(f"\r[✓] CONNECTED — {scene_name}          ", end="", flush=True)
                    except Exception:
                        pass

                time.sleep(0.5)
        finally:
            print()
            logger.info("Shutting down...")
            dcc_mcp_photoshop.stop_server()
            print("Server stopped.")
    else:
        # Bridge-only mode (default, for deployment)
        print("  [BRIDGE-ONLY MODE] Requires dcc-mcp-server.exe running separately")
        print(f"  WS bridge   : ws://{args.ws_host}:{args.ws_port}")
        print(f"  RPC endpoint: http://{args.ws_host}:{args.rpc_port}/rpc")
        print()
        print("MCP clients: http://127.0.0.1:8765/mcp (direct) or http://127.0.0.1:9765/mcp/dcc/photoshop (gateway)")
        print()
        print("Waiting for Photoshop UXP plugin to connect...")
        print("Press Ctrl+C to stop.\n")

        bridge = dcc_mcp_photoshop.start_bridge_only(
            ws_host=args.ws_host,
            ws_port=args.ws_port,
            rpc_port=args.rpc_port,
        )

        logger.info("Bridge plugin started on ws://%s:%d", args.ws_host, args.ws_port)

        last_status = None
        last_scene = None
        try:
            while not stop[0]:
                connected = is_photoshop_available()
                status = "CONNECTED" if connected else "waiting for UXP plugin..."
                if status != last_status:
                    sym = "✓" if connected else "○"
                    print(f"\r[{sym}] {status}          ", end="", flush=True)
                    last_status = status

                if connected:
                    try:
                        bridge = get_bridge()
                        doc_info = bridge.call("ps.getDocumentInfo")
                        scene_name = doc_info.get("name") if isinstance(doc_info, dict) else None
                        if scene_name and scene_name != last_scene:
                            _update_scene(scene_name)
                            last_scene = scene_name
                            print(f"\r[✓] CONNECTED — {scene_name}          ", end="", flush=True)
                    except Exception:
                        pass

                time.sleep(0.5)
        finally:
            print()
            logger.info("Shutting down...")
            dcc_mcp_photoshop.stop_bridge_only()
            print("Bridge stopped.")


if __name__ == "__main__":
    main()
