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

Protocol
--------
  Python → UXP  (request):
    {"jsonrpc":"2.0","id":1,"method":"ps.getDocumentInfo","params":{}}

  UXP → Python  (response):
    {"jsonrpc":"2.0","id":1,"result":{"name":"Untitled-1.psd",...}}

  UXP → Python  (error):
    {"jsonrpc":"2.0","id":1,"error":{"code":-32603,"message":"..."}}

  UXP → Python  (hello, on connect):
    {"type":"hello","client":"photoshop-uxp","version":"0.1.0"}
"""

from __future__ import annotations

import asyncio
import json
import logging
import logging.handlers
import os
import threading
from concurrent.futures import Future
from pathlib import Path
from typing import Any, Dict, Optional

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
        data: Optional extra data.
    """

    def __init__(self, message: str, code: int = -32603, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
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
        self._uxp_connect_count = 0   # cumulative connect events
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
                self._loop.run_until_complete(
                    self._serve(ready_event, uxp_connected_event, start_exc)
                )
                self._loop.run_forever()
            except Exception:
                pass
            finally:
                self._loop.close()

        self._thread = threading.Thread(
            target=_run_loop, daemon=True, name="photoshop-bridge-server"
        )
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

                # Handle non-RPC hello message
                if msg.get("type") == "hello":
                    logger.info(
                        "UXP plugin hello: %s v%s",
                        msg.get("client"),
                        msg.get("version"),
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
                self._set_future_exception(
                    f, BridgeConnectionError("UXP plugin disconnected")
                )
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
        except TimeoutError:
            self._pending.pop(req_id, None)
            logger.warning("call id=%d method=%s TIMEOUT after %.1fs", req_id, method, self._timeout)
            raise BridgeTimeoutError(
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

    def __enter__(self) -> "PhotoshopBridge":
        self.connect()
        return self

    def __exit__(self, *args: Any) -> None:
        self.disconnect()
