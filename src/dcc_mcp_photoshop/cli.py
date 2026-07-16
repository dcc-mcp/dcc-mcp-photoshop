"""dcc-mcp-photoshop CLI — start the MCP server with adobepy broker.

This module is the entry point for:
- ``python -m dcc_mcp_photoshop``
- ``dcc-mcp-photoshop`` (pip entry-point)

The server uses the adobepy Rust broker (default ``http://127.0.0.1:47391``)
to communicate with Photoshop.  Skill scripts use ``adobe.photoshop.Photoshop()``
facade which connects to the same broker.

Usage::

    # Start the MCP server
    python -m dcc_mcp_photoshop

    # MCP clients normally connect through the stable gateway on port 9765.

Requirements:
    - adobepy Rust broker running (``adobepy broker``)
    - adobepy UXP bridge installed in Photoshop
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dcc_mcp_photoshop.config import PhotoshopMcpConfig

logger = logging.getLogger(__name__)


def _setup_logging(verbose: bool, log_level: str | None = None) -> None:
    level_name = log_level or ("DEBUG" if verbose else "INFO")
    level = getattr(logging, level_name.upper(), logging.INFO)
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
            "DCC MCP Server for Adobe Photoshop\n\n"
            "Uses adobepy Rust broker to communicate with Photoshop.\n"
            "Requires: adobepy broker + UXP bridge running."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  dcc-mcp-photoshop
  python -m dcc_mcp_photoshop --mcp-port 8766 --broker-url http://127.0.0.1:47391

Environment variables:
  ADOBEPY_BROKER_URL            Broker HTTP endpoint (default: http://127.0.0.1:47391)
  ADOBEPY_TOKEN                 Auth token (default: dev-token)
  DCC_MCP_PHOTOSHOP_PORT        Optional fixed MCP instance port (default: OS-assigned)
  DCC_MCP_GATEWAY_PORT          Gateway competition port
  DCC_MCP_PHOTOSHOP_LOG_DIR     Log directory (default: ~/.dcc-mcp/logs)
  DCC_MCP_PHOTOSHOP_LOG_LEVEL   Log level (default: INFO)
  DCC_MCP_PHOTOSHOP_TIMEOUT     Timeout in seconds (default: 30.0)
""",
    )
    parser.add_argument(
        "--mcp-port",
        type=int,
        default=None,
        help="MCP instance port (default: operating-system assigned)",
    )
    parser.add_argument(
        "--broker-url",
        default=None,
        help="adobepy broker URL (default: ADOBEPY_BROKER_URL env or http://127.0.0.1:47391)",
    )
    parser.add_argument(
        "--gateway-port",
        type=int,
        default=None,
        help="Gateway competition port (default: env DCC_MCP_GATEWAY_PORT or disabled)",
    )
    parser.add_argument(
        "--server-name",
        default="photoshop-mcp",
        help="Server name reported in MCP (default: photoshop-mcp)",
    )
    parser.add_argument(
        "--skill-paths",
        nargs="*",
        default=[],
        metavar="PATH",
        help="Extra skill directories",
    )
    parser.add_argument(
        "--no-builtins",
        action="store_true",
        help="Do not discover built-in skills",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_get_version()}",
    )
    return parser


def _get_version() -> str:
    try:
        from dcc_mcp_photoshop.__version__ import __version__  # noqa: PLC0415

        return __version__
    except Exception:
        return "0.0.0"


def _run_server(args: argparse.Namespace, config: PhotoshopMcpConfig) -> None:
    print(f"dcc-mcp-photoshop v{_get_version()}")
    print(f"  Broker      : {config.broker_url}")
    print()
    print("Requires adobepy broker + UXP bridge running in Photoshop.")
    print("Press Ctrl+C to stop.\n")

    import dcc_mcp_photoshop.server as _server_mod  # noqa: PLC0415

    stop = [False]

    def _on_signal(*_):
        stop[0] = True

    signal.signal(signal.SIGINT, _on_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _on_signal)

    handle, startup_state = _server_mod.run_daemon(
        port=args.mcp_port,
        server_name=args.server_name,
        broker_url=config.broker_url,
        gateway_port=args.gateway_port,
        register_builtins=not args.no_builtins,
        extra_skill_paths=args.skill_paths or None,
    )

    mcp_url = handle.mcp_url() if hasattr(handle, "mcp_url") else str(handle)
    logger.info("MCP server started at %s  (startup_state=%s)", mcp_url, startup_state.stage)
    print(f"  MCP server  : {mcp_url}")

    if startup_state.stage == "failed":
        logger.error(
            "Startup FAILED at stage=%s: %s",
            startup_state.failure_stage,
            startup_state.recommended_next_action,
        )

    print("Running... Press Ctrl+C to stop.\n")
    try:
        while not stop[0]:
            time.sleep(1)
    finally:
        logger.info("Shutting down...")
        _server_mod.stop_server()
        print("Server stopped.")


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    from dcc_mcp_photoshop.config import PhotoshopMcpConfig  # noqa: PLC0415

    config = PhotoshopMcpConfig.from_env()
    if args.broker_url:
        config.broker_url = args.broker_url

    _setup_logging(args.verbose, config.log_level)

    from dcc_mcp_photoshop._single_instance import (  # noqa: PLC0415
        AlreadyRunningError,
        SingleInstanceLease,
    )

    try:
        with SingleInstanceLease():
            _run_server(args, config)
    except AlreadyRunningError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
