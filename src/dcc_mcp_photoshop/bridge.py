"""PhotoshopBridge — Python WebSocket server that the UXP plugin connects to.

Architecture (corrected — UXP cannot act as WS server)
--------------------------------------------------------
  MCP Client  ──HTTP──►  PhotoshopMcpServer  ──call()──►  PhotoshopBridge
                                                                  │
                                              Python WS server :9001
                                                                  │
                                              Photoshop UXP plugin (WS CLIENT)
                                                                  │
                                              Photoshop UXP API

Flow:
  1. Python starts a WebSocket server on localhost:9001.
  2. The Photoshop UXP plugin connects to it as a WebSocket CLIENT.
  3. Python sends JSON-RPC 2.0 requests; UXP executes and replies.
  4. ``bridge.call("ps.getDocumentInfo")`` blocks until UXP responds.

Why inverted?
  UXP only supports WebSocket CLIENT, not server.
  See: https://forums.creativeclouddeveloper.com/t/7423

Protocol (v0.1.0)
------------------
  Python → UXP  (request):
    {"jsonrpc":"2.0","id":1,"method":"ps.getDocumentInfo","params":{}}

  UXP → Python  (response):
    {"jsonrpc":"2.0","id":1,"result":{"name":"Untitled-1.psd",...}}

  UXP → Python  (error):
    {"jsonrpc":"2.0","id":1,"error":{"code":-32603,"message":"...","hint":"..."}}

  UXP → Python  (progress):
    {"jsonrpc":"2.0","id":1,"type":"progress","progress":{"current":50,"total":100}}

  UXP → Python  (hello, on connect):
    {"type":"hello","protocol":"photoshop-bridge","version":"0.1.0","client":"photoshop-uxp"}

  Python → UXP  (hello_ack):
    {"type":"hello_ack","protocol":"photoshop-bridge","version":"0.1.0"}

  Python → UXP  (disconnected):
    {"type":"disconnected","reason":"Server stopped"}

See docs/bridge-protocol.md for the full specification.
"""

from __future__ import annotations

import asyncio
import json
import logging
import logging.handlers
import threading
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FutureTimeoutError
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, Optional

from dcc_mcp_photoshop.protocol import (
    build_disconnected,
    build_hello_ack,
    is_hello,
    is_progress,
)

logger = logging.getLogger(__name__)

# Python WebSocket server port — UXP plugin connects to this
DEFAULT_SERVER_HOST = "localhost"
DEFAULT_SERVER_PORT = 9001
DEFAULT_TIMEOUT_SEC = 30.0

# Default bridge log path — rotate at 5 MB, keep 5 backups
_DEFAULT_LOG_DIR = Path.home() / ".dcc-mcp" / "logs"
_BRIDGE_LOG_FILENAME = "photoshop-bridge.log"


def _setup_file_logger(log_dir: Path = _DEFAULT_LOG_DIR) -> None:
    """Configure a rotating file handler for the bridge logger.

    Creates ``~/.dcc-mcp/logs/photoshop-bridge.log`` (rotates at 5 MB,
    keeps 5 backups).  Safe to call multiple times — handler is only added
    once.
    """
    for h in logger.handlers:
        if isinstance(h, logging.handlers.RotatingFileHandler):
            return  # already configured

    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / _BRIDGE_LOG_FILENAME

    handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    # Ensure the logger level allows DEBUG messages through
    if logger.level == logging.NOTSET or logger.level > logging.DEBUG:
        logger.setLevel(logging.DEBUG)

    logger.info("Bridge log file: %s", log_path)


# ---------------------------------------------------------------------------
# Exception types
# ---------------------------------------------------------------------------


class BridgeConnectionError(ConnectionError):
    """Raised when the UXP plugin has not yet connected to the Python server."""


class BridgeTimeoutError(TimeoutError):
    """Raised when a bridge call does not receive a response within the timeout."""


class BridgeRpcError(RuntimeError):
    """Raised when the UXP plugin returns a JSON-RPC error response.

    Attributes:
        code: JSON-RPC error code.
        hint: Actionable suggestion from the UXP side.
        data: Optional extra diagnostic data.
    """

    def __init__(self, message: str, code: int = -32603, hint: str = "", data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.hint = hint
        self.data = data


# ---------------------------------------------------------------------------
# PhotoshopBridge
# ---------------------------------------------------------------------------


class PhotoshopBridge:
    """Python WebSocket server that Photoshop UXP connects to.

    Starts a WebSocket server in a background thread.  When the UXP plugin
    connects, Python can send JSON-RPC 2.0 requests and receive responses
    via the synchronous ``call()`` method.

    Args:
        host: Hostname for the server (default ``"localhost"``).
        port: Port for the server (default ``9001``).
        timeout: Per-call timeout in seconds (default ``30.0``).

    Example::

        bridge = PhotoshopBridge()
        bridge.connect()                          # start server + wait for UXP
        info = bridge.call("ps.getDocumentInfo")  # synchronous
        bridge.disconnect()
    """

    def __init__(
        self,
        host: str = DEFAULT_SERVER_HOST,
        port: int = DEFAULT_SERVER_PORT,
        timeout: float = DEFAULT_TIMEOUT_SEC,
        log_dir: Optional[Path] = None,
    ) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout

        # Set up rotating file logger for persistent debug output
        _setup_file_logger(log_dir or _DEFAULT_LOG_DIR)

        # Background event loop (owns the WS server)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._server = None  # asyncio WS server

        # Active UXP connection (set on first client connect)
        self._uxp_ws = None
        self._connected = False  # True once UXP plugin has connected
        self._uxp_connect_count = 0  # cumulative connect events
        self._uxp_disconnect_count = 0  # cumulative disconnect events

        # Pending RPC calls: id → Future
        self._pending: Dict[int, Future] = {}
        self._request_id = 0
        self._id_lock = threading.Lock()

    # ── Properties ────────────────────────────────────────────────────────

    @property
    def endpoint(self) -> str:
        """WebSocket server endpoint URL."""
        return f"ws://{self._host}:{self._port}"

    def is_connected(self) -> bool:
        """Return ``True`` if the UXP plugin is currently connected."""
        return self._connected and self._uxp_ws is not None

    # ── Server lifecycle ──────────────────────────────────────────────────

    def connect(self, wait_for_uxp: bool = False) -> None:
        """Start the WebSocket server.

        The server starts immediately.  The UXP plugin will connect
        when Photoshop loads the plugin.

        Args:
            wait_for_uxp: If ``True``, block until the UXP plugin connects
                (or ``timeout`` seconds elapse).  Default is ``False`` —
                start the server and return immediately.

        Raises:
            BridgeConnectionError: If ``wait_for_uxp=True`` and UXP does not
                connect within the timeout.
        """
        if self._loop is not None:
            logger.debug("PhotoshopBridge server already running at %s", self.endpoint)
            return

        self._loop = asyncio.new_event_loop()
        ready_event = threading.Event()
        uxp_connected_event = threading.Event()
        start_exc: list = []

        def _run_loop() -> None:
            asyncio.set_event_loop(self._loop)
            try:
                self._loop.run_until_complete(self._serve(ready_event, uxp_connected_event, start_exc))
                self._loop.run_forever()
            except Exception:
                pass
            finally:
                self._loop.close()

        self._thread = threading.Thread(target=_run_loop, daemon=True, name="photoshop-bridge-server")
        self._thread.start()

        # Wait until server is listening
        ready_event.wait(timeout=5)
        if start_exc:
            raise BridgeConnectionError(
                f"Failed to start WebSocket server on {self.endpoint}: {start_exc[0]}"
            ) from start_exc[0]

        logger.info(
            "PhotoshopBridge server listening at %s — waiting for UXP plugin to connect",
            self.endpoint,
        )

        if wait_for_uxp:
            if not uxp_connected_event.wait(timeout=self._timeout):
                raise BridgeConnectionError(
                    f"UXP plugin did not connect within {self._timeout}s. "
                    "Ensure Photoshop is running with the dcc-mcp UXP plugin enabled."
                )

    async def _serve(
        self,
        ready_event: threading.Event,
        uxp_connected_event: threading.Event,
        exc_out: list,
    ) -> None:
        """Coroutine: start the WS server, then signal the calling thread."""
        try:
            import websockets  # noqa: PLC0415

            self._server = await websockets.serve(
                lambda ws: self._handle_uxp(ws, uxp_connected_event),
                self._host,
                self._port,
            )
        except Exception as exc:
            exc_out.append(exc)
        finally:
            ready_event.set()

    async def _handle_uxp(self, websocket, uxp_connected_event: threading.Event) -> None:
        """Handle a single UXP plugin connection."""
        self._uxp_connect_count += 1
        logger.info(
            "UXP plugin connected from %s (session #%d)",
            websocket.remote_address,
            self._uxp_connect_count,
        )
        self._uxp_ws = websocket
        self._connected = True
        uxp_connected_event.set()

        try:
            async for raw in websocket:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning("PhotoshopBridge: invalid JSON from UXP: %r", raw[:200])
                    continue

                # Handle hello handshake
                if is_hello(msg):
                    reconnect = " (reconnect)" if msg.get("reconnect") else ""
                    logger.info(
                        "UXP plugin hello: %s v%s%s",
                        msg.get("client"),
                        msg.get("version"),
                        reconnect,
                    )
                    try:
                        await websocket.send(json.dumps(build_hello_ack()))
                    except Exception:
                        pass
                    continue

                # Handle progress notification — log but do NOT resolve pending future
                if is_progress(msg):
                    p = msg.get("progress", {})
                    logger.debug(
                        "Progress id=%r %d/%d%s",
                        msg.get("id"),
                        p.get("current", 0),
                        p.get("total", 0),
                        f" — {p['message']}" if p.get("message") else "",
                    )
                    continue

                # Route JSON-RPC response back to waiting caller
                req_id = msg.get("id")
                future = self._pending.pop(req_id, None) if req_id is not None else None

                if future is None:
                    logger.debug("PhotoshopBridge: unsolicited message id=%r", req_id)
                    continue

                if "error" in msg:
                    err_info = msg["error"]
                    logger.debug(
                        "PhotoshopBridge: RPC error id=%r code=%s msg=%s",
                        req_id,
                        err_info.get("code"),
                        err_info.get("message"),
                    )
                    exc = BridgeRpcError(
                        err_info.get("message", "Unknown RPC error"),
                        code=err_info.get("code", -32603),
                        hint=err_info.get("hint", ""),
                        data=err_info.get("data"),
                    )
                    self._set_future_exception(future, exc)
                else:
                    logger.debug("PhotoshopBridge: RPC success id=%r", req_id)
                    self._set_future_result(future, msg.get("result"))

        except Exception as exc:
            logger.warning("PhotoshopBridge: UXP connection closed: %s", exc)
        finally:
            self._uxp_disconnect_count += 1
            self._uxp_ws = None
            self._connected = False
            # Fail all pending calls
            for f in self._pending.values():
                self._set_future_exception(f, BridgeConnectionError("UXP plugin disconnected"))
            self._pending.clear()
            logger.info("UXP plugin disconnected")

    @staticmethod
    def _set_future_result(future: Future, result: Any) -> None:
        if not future.done():
            future.set_result(result)

    @staticmethod
    def _set_future_exception(future: Future, exc: Exception) -> None:
        if not future.done():
            future.set_exception(exc)

    def disconnect(self) -> None:
        """Stop the WebSocket server and close the UXP connection."""
        self._connected = False

        if self._loop is not None:

            async def _close():
                if self._uxp_ws:
                    try:
                        await self._uxp_ws.send(json.dumps(build_disconnected()))
                    except Exception:
                        pass
                if self._server:
                    self._server.close()
                    await self._server.wait_closed()
                if self._uxp_ws:
                    await self._uxp_ws.close()

            if not self._loop.is_closed():
                try:
                    asyncio.run_coroutine_threadsafe(_close(), self._loop).result(timeout=5)
                except Exception:
                    pass
                self._loop.call_soon_threadsafe(self._loop.stop)

        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

        self._loop = None
        self._server = None
        self._uxp_ws = None
        logger.info("PhotoshopBridge server stopped")

    # ── RPC call ──────────────────────────────────────────────────────────

    def call(self, method: str, **params: Any) -> Any:
        """Send a JSON-RPC request to the UXP plugin and return the result.

        Blocks until the response arrives or the timeout expires.

        Args:
            method: JSON-RPC method name (e.g. ``"ps.getDocumentInfo"``).
            **params: Method keyword parameters.

        Returns:
            The ``result`` field from the JSON-RPC success response.

        Raises:
            BridgeConnectionError: If the UXP plugin is not connected.
            BridgeTimeoutError: If no response arrives within ``timeout`` seconds.
            BridgeRpcError: If the UXP plugin returns a JSON-RPC error.

        Example::

            info = bridge.call("ps.getDocumentInfo")
            layers = bridge.call("ps.listLayers", include_hidden=True)
        """
        if not self.is_connected() or self._loop is None:
            raise BridgeConnectionError(
                "Photoshop UXP plugin is not connected. "
                "Ensure Photoshop is running, the dcc-mcp UXP plugin is enabled, "
                "and start_server() has been called."
            )

        with self._id_lock:
            self._request_id += 1
            req_id = self._request_id

        request = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }

        logger.debug("→ call id=%d method=%s params=%r", req_id, method, params)

        future: Future = Future()
        self._pending[req_id] = future

        async def _send():
            try:
                await self._uxp_ws.send(json.dumps(request))
            except Exception as exc:
                self._pending.pop(req_id, None)
                self._set_future_exception(future, BridgeConnectionError(str(exc)))

        asyncio.run_coroutine_threadsafe(_send(), self._loop)

        try:
            result = future.result(timeout=self._timeout)
            logger.debug("← call id=%d method=%s OK", req_id, method)
            return result
        except FutureTimeoutError:
            self._pending.pop(req_id, None)
            logger.warning("call id=%d method=%s TIMEOUT after %.1fs", req_id, method, self._timeout)
            raise BridgeTimeoutError(  # noqa: B904
                f"call({method!r}) timed out after {self._timeout}s. "
                "Check that Photoshop and the dcc-mcp UXP plugin are responding."
            )

    # ── Convenience helpers ────────────────────────────────────────────────

    def execute_script(self, code: str) -> Any:
        """Execute a JavaScript/UXP expression in Photoshop."""
        return self.call("ps.executeScript", code=code)

    def get_document_info(self) -> Dict[str, Any]:
        """Return metadata for the active Photoshop document."""
        return self.call("ps.getDocumentInfo")

    def list_documents(self) -> list:
        """Return a list of all open Photoshop documents."""
        return self.call("ps.listDocuments")

    def list_layers(self, include_hidden: bool = True) -> list:
        """Return the layer tree for the active document."""
        return self.call("ps.listLayers", include_hidden=include_hidden)

    # ── Context manager ────────────────────────────────────────────────────

    def __enter__(self) -> PhotoshopBridge:
        self.connect()
        return self

    def __exit__(self, *args: Any) -> None:
        self.disconnect()


# ---------------------------------------------------------------------------
# BridgeRpcServer — exposes the bridge via HTTP for cross-process access
# ---------------------------------------------------------------------------


class BridgeRpcServer:
    """Lightweight HTTP RPC server that wraps ``PhotoshopBridge`` for cross-process access.

    Skill scripts running inside ``dcc-mcp-server.exe`` connect to this HTTP
    endpoint to call the bridge via JSON-RPC over HTTP POST.

    The server runs in a background daemon thread and exposes:
      - ``POST /rpc`` — JSON-RPC 2.0 request, forwarded to the bridge
      - ``GET /healthz`` — health check (returns 200 OK)

    Args:
        bridge: The ``PhotoshopBridge`` instance to wrap.
        host: Hostname to bind to (default ``"localhost"``).
        port: TCP port (default ``9100``).

    Example::

        server = BridgeRpcServer(bridge, port=9100)
        server.start()
        # ... server runs in background ...
        server.stop()
    """

    def __init__(
        self,
        bridge: PhotoshopBridge,
        host: str = "localhost",
        port: int = 9100,
    ) -> None:
        self._bridge = bridge
        self._host = host
        self._port = port
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def endpoint(self) -> str:
        """HTTP server endpoint URL."""
        return f"http://{self._host}:{self._port}/rpc"

    def start(self) -> None:
        """Start the HTTP RPC server in a background daemon thread.

        The server binds immediately.  If the port is unavailable, a warning
        is logged and the server is not started (the bridge itself still works,
        but cross-process RPC will not be available).
        """
        if self._server is not None:
            logger.debug("BridgeRpcServer already running at %s", self.endpoint)
            return

        _bridge_ref = self._bridge

        class _Handler(BaseHTTPRequestHandler):
            # Silence per-request logs by default — the logger handles it
            _bridge = _bridge_ref

            def log_message(self, fmt, *args):
                logger.debug("BridgeRpcServer: %s", fmt % args)

            def _send_json(self, status: int, body: dict) -> None:
                data = json.dumps(body).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _send_error(self, status: int, message: str) -> None:
                self._send_json(status, {"error": message})

            def do_GET(self):
                if self.path == "/healthz":
                    self._send_json(HTTPStatus.OK, {"status": "ok"})
                else:
                    self._send_error(HTTPStatus.NOT_FOUND, "Not found")

            def do_POST(self):
                if self.path != "/rpc":
                    self._send_error(HTTPStatus.NOT_FOUND, "Not found")
                    return

                content_length = int(self.headers.get("Content-Length", 0))
                if content_length == 0:
                    self._send_error(HTTPStatus.BAD_REQUEST, "Empty request body")
                    return

                try:
                    raw = self.rfile.read(content_length)
                    req = json.loads(raw)
                except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                    self._send_error(HTTPStatus.BAD_REQUEST, f"Invalid JSON: {exc}")
                    return

                method = req.get("method")
                if not method:
                    self._send_error(HTTPStatus.BAD_REQUEST, "Missing 'method' field")
                    return

                params = req.get("params", {})
                req_id = req.get("id", 0)

                try:
                    result = self._bridge.call(method, **params)
                    self._send_json(
                        HTTPStatus.OK,
                        {"jsonrpc": "2.0", "id": req_id, "result": result},
                    )
                except BridgeConnectionError as exc:
                    self._send_json(
                        HTTPStatus.SERVICE_UNAVAILABLE,
                        {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "error": {"code": -32007, "message": str(exc)},
                        },
                    )
                except BridgeTimeoutError as exc:
                    self._send_json(
                        HTTPStatus.GATEWAY_TIMEOUT,
                        {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "error": {"code": -32006, "message": str(exc)},
                        },
                    )
                except BridgeRpcError as exc:
                    self._send_json(
                        HTTPStatus.OK,
                        {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "error": {"code": exc.code, "message": str(exc), "hint": exc.hint},
                        },
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.exception("BridgeRpcServer: unhandled error in POST /rpc")
                    self._send_json(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "error": {"code": -32603, "message": f"Internal error: {exc}"},
                        },
                    )

        try:
            self._server = HTTPServer((self._host, self._port), _Handler)
        except OSError as exc:
            logger.warning(
                "BridgeRpcServer could not bind to %s:%d: %s — "
                "cross-process RPC will not be available",
                self._host,
                self._port,
                exc,
            )
            self._server = None
            return

        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name="bridge-rpc-server",
        )
        self._thread.start()
        logger.info(
            "BridgeRpcServer listening at http://%s:%d/rpc",
            self._host,
            self._port,
        )

    def stop(self) -> None:
        """Stop the HTTP RPC server."""
        if self._server is not None:
            logger.info("BridgeRpcServer stopping")
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("BridgeRpcServer stopped")
