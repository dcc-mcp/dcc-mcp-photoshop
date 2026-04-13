"""dcc-mcp-photoshop CLI — standalone MCP + WebSocket bridge server.

This module is the entry point for:
- ``python -m dcc_mcp_photoshop``
- ``dcc-mcp-photoshop`` (pip entry-point)
- ``dcc-mcp-photoshop.exe`` (PyInstaller single-file build)

Architecture
------------
When run as a standalone process, this server:

1. Starts the MCP HTTP server on ``--mcp-port`` (default 8765)
   → Claude / Cursor / any MCP client connects here

2. Starts the WebSocket bridge server on ``--ws-port`` (default 9001)
   → The Photoshop UXP plugin connects here as a WebSocket CLIENT

3. Loads skill scripts from ``--skill-paths`` or the built-in skills directory
   → Skill scripts call ``ps.*`` methods via the bridge

No Python environment is required by the end user when distributed as
a PyInstaller binary.
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
            "DCC MCP Server for Adobe Photoshop\n\n"
            "Starts an MCP HTTP server (for AI clients) and a WebSocket bridge\n"
            "server (for the Photoshop UXP plugin). No Python required on the\n"
            "target machine when distributed as a binary."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  dcc-mcp-photoshop                          # default ports
  dcc-mcp-photoshop --mcp-port 9000          # custom MCP port
  dcc-mcp-photoshop --ws-port 9002           # custom WebSocket port
  dcc-mcp-photoshop --skill-paths /my/skills # extra skill directory
  dcc-mcp-photoshop --verbose                # debug logging

Environment variables:
  DCC_MCP_PHOTOSHOP_SKILL_PATHS   Extra skill directories (path separator)
  DCC_MCP_SKILL_PATHS             Global skill directories
""",
    )
    parser.add_argument(
        "--mcp-port", type=int, default=8765,
        help="MCP HTTP server port (default: 8765)",
    )
    parser.add_argument(
        "--ws-port", type=int, default=9001,
        help="WebSocket bridge server port for UXP plugin (default: 9001)",
    )
    parser.add_argument(
        "--ws-host", default="localhost",
        help="WebSocket bind host (default: localhost)",
    )
    parser.add_argument(
        "--server-name", default="photoshop-mcp",
        help="Server name reported in MCP initialize (default: photoshop-mcp)",
    )
    parser.add_argument(
        "--skill-paths", nargs="*", default=[],
        metavar="PATH",
        help="Additional skill directories to load",
    )
    parser.add_argument(
        "--no-builtins", action="store_true",
        help="Do not load built-in Photoshop skills",
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
    print(f"  MCP server  : http://localhost:{args.mcp_port}/mcp")
    print(f"  WS bridge   : ws://{args.ws_host}:{args.ws_port}  (UXP plugin connects here)")
    print()
    print("Waiting for Photoshop UXP plugin to connect...")
    print("Press Ctrl+C to stop.\n")

    import dcc_mcp_photoshop  # noqa: PLC0415

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


if __name__ == "__main__":
    main()
