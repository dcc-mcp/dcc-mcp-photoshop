"""dcc-mcp-photoshop CLI — bridge-only plugin for use with dcc-mcp-server.exe.

This module is the entry point for:
- ``python -m dcc_mcp_photoshop``
- ``dcc-mcp-photoshop`` (pip entry-point)
- ``dcc-mcp-photoshop.exe`` (PyInstaller single-file build)

Architecture (recommended: gateway mode)
----------------------------------------
In gateway mode (dcc-mcp-core v0.12.23+), use:

  dcc-mcp-server.exe --dcc photoshop --skill-paths ./src/dcc_mcp_photoshop/skills
  python -m dcc_mcp_photoshop --ws-port 9001

The server process handles:
  - MCP HTTP on port 8765 (configurable)
  - Skill discovery and lazy loading

This plugin only maintains:
  - WebSocket bridge on port 9001 (configurable)
  - UXP plugin connection lifecycle

Benefits:
  - Progressive skill loading (smaller initial tool list)
  - Better scalability (separate server process)
  - Isolated resource management

Legacy mode (deprecated)
------------------------
For backwards compatibility, ``--legacy`` mode starts the old embedded server:

  python -m dcc_mcp_photoshop --legacy --mcp-port 8765 --ws-port 9001

This eagerly loads all skills at startup (not recommended).
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
    # Quieten noisy dcc-mcp-core Rust log spam at INFO level
    if not verbose:
        logging.getLogger("dcc_mcp_core").setLevel(logging.WARNING)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dcc-mcp-photoshop",
        description=(
            "DCC MCP Bridge Plugin for Adobe Photoshop\n\n"
            "Gateway mode (recommended, requires dcc-mcp-core v0.12.23+):\n"
            "  1. Start dcc-mcp-server.exe --dcc photoshop --skill-paths ./skills\n"
            "  2. Start this plugin to maintain WebSocket bridge to Photoshop\n\n"
            "Legacy mode (deprecated, embedded MCP server):\n"
            "  python -m dcc_mcp_photoshop --legacy"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples (gateway mode — recommended):
  dcc-mcp-server.exe --dcc photoshop --skill-paths ./skills
  python -m dcc_mcp_photoshop --ws-port 9001

Examples (legacy mode — deprecated):
  python -m dcc_mcp_photoshop --legacy
  python -m dcc_mcp_photoshop --legacy --mcp-port 9000 --no-builtins

Environment variables:
  DCC_MCP_PHOTOSHOP_SKILL_PATHS   Extra skill directories (legacy mode)
  DCC_MCP_SKILL_PATHS             Global skill directories (legacy mode)
""",
    )
    parser.add_argument(
        "--legacy", action="store_true",
        help="Use legacy embedded MCP server (deprecated, use dcc-mcp-server.exe instead)",
    )
    parser.add_argument(
        "--mcp-port", type=int, default=8765,
        help="MCP HTTP server port (legacy mode only; default: 8765)",
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
        "--server-name", default="photoshop-mcp",
        help="Server name reported in MCP (legacy mode only; default: photoshop-mcp)",
    )
    parser.add_argument(
        "--skill-paths", nargs="*", default=[],
        metavar="PATH",
        help="Extra skill directories (legacy mode only)",
    )
    parser.add_argument(
        "--no-builtins", action="store_true",
        help="Do not load built-in skills (legacy mode only)",
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

    if args.legacy:
        # Legacy embedded MCP server mode (deprecated)
        print("  [LEGACY MODE] Embedded MCP server (deprecated)")
        print(f"  MCP server  : http://localhost:{args.mcp_port}/mcp")
        print(f"  WS bridge   : ws://{args.ws_host}:{args.ws_port}  (UXP plugin connects here)")
        print()
        logger.warning(
            "LEGACY MODE: Use dcc-mcp-server.exe --dcc photoshop in gateway mode instead"
        )
        print("Waiting for Photoshop UXP plugin to connect...")
        print("Press Ctrl+C to stop.\n")

        handle = dcc_mcp_photoshop.start_server(
            port=args.mcp_port,
            server_name=args.server_name,
            ws_host=args.ws_host,
            ws_port=args.ws_port,
            register_builtins=not args.no_builtins,
            extra_skill_paths=args.skill_paths or None,
        )

        logger.info("MCP server started at %s", handle.mcp_url())

        # Handle Ctrl+C gracefully
        stop = [False]

        def _on_signal(*_):
            stop[0] = True

        signal.signal(signal.SIGINT, _on_signal)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _on_signal)

        from dcc_mcp_photoshop.api import is_photoshop_available  # noqa: PLC0415

        last_status = None
        try:
            while not stop[0]:
                connected = is_photoshop_available()
                status = "CONNECTED" if connected else "waiting for UXP plugin..."
                if status != last_status:
                    sym = "✓" if connected else "○"
                    print(f"\r[{sym}] {status}          ", end="", flush=True)
                    last_status = status
                time.sleep(0.5)
        finally:
            print()
            logger.info("Shutting down...")
            dcc_mcp_photoshop.stop_server()
            print("Server stopped.")
    else:
        # Gateway mode (recommended)
        print("  [GATEWAY MODE] Bridge-only plugin (requires dcc-mcp-server.exe)")
        print(f"  WS bridge   : ws://{args.ws_host}:{args.ws_port}  (UXP plugin connects here)")
        print()
        print("Waiting for Photoshop UXP plugin to connect...")
        print("Press Ctrl+C to stop.\n")

        bridge = dcc_mcp_photoshop.start_bridge_only(
            ws_host=args.ws_host,
            ws_port=args.ws_port,
        )

        logger.info("Bridge plugin started, listening on ws://%s:%d", args.ws_host, args.ws_port)

        # Handle Ctrl+C gracefully
        stop = [False]

        def _on_signal(*_):
            stop[0] = True

        signal.signal(signal.SIGINT, _on_signal)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _on_signal)

        from dcc_mcp_photoshop.api import is_photoshop_available  # noqa: PLC0415

        last_status = None
        try:
            while not stop[0]:
                connected = is_photoshop_available()
                status = "CONNECTED" if connected else "waiting for UXP plugin..."
                if status != last_status:
                    sym = "✓" if connected else "○"
                    print(f"\r[{sym}] {status}          ", end="", flush=True)
                    last_status = status
                time.sleep(0.5)
        finally:
            print()
            logger.info("Shutting down...")
            dcc_mcp_photoshop.stop_bridge_only()
            print("Bridge stopped.")


if __name__ == "__main__":
    main()
