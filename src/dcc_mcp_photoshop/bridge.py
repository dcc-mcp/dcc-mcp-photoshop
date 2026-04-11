"""PhotoshopBridge — WebSocket client that communicates with the Photoshop UXP plugin.

Protocol
--------
The UXP plugin opens a WebSocket server. This bridge sends JSON-RPC 2.0 messages
and receives responses:

  Request:  {"jsonrpc": "2.0", "id": 1, "method": "ps.executeScript", "params": {"code": "..."}}
  Response: {"jsonrpc": "2.0", "id": 1, "result": {...}} or {"error": {...}}

Supported methods (UXP plugin implements these):
  - ps.executeScript(code: str) -> any
  - ps.getDocumentInfo() -> dict
  - ps.listDocuments() -> list
  - ps.executeAction(action: str, descriptor: dict) -> dict
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Default UXP WebSocket port
DEFAULT_WS_PORT = 3000
DEFAULT_WS_HOST = "localhost"
DEFAULT_TIMEOUT_SEC = 30.0


class BridgeConnectionError(ConnectionError):
    """Raised when the bridge cannot connect to the Photoshop UXP WebSocket."""


class BridgeTimeoutError(TimeoutError):
    """Raised when a bridge call times out."""


class PhotoshopBridge:
    """WebSocket bridge to the Photoshop UXP plugin.

    This class is intentionally synchronous — it manages its own event loop
    in a background thread so the calling code (dcc-mcp-core action handlers)
    stays synchronous.

    Usage::

        bridge = PhotoshopBridge(host="localhost", port=3000)
        bridge.connect()
        result = bridge.call("ps.getDocumentInfo")
        bridge.disconnect()

    Or as a context manager::

        with PhotoshopBridge() as bridge:
            result = bridge.call("ps.executeScript", code="app.documents.length")
    """

    def __init__(
        self,
        host: str = DEFAULT_WS_HOST,
        port: int = DEFAULT_WS_PORT,
        timeout: float = DEFAULT_TIMEOUT_SEC,
    ) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout
        self._ws = None
        self._connected = False
        self._lock = threading.Lock()
        self._request_id = 0

    @property
    def endpoint(self) -> str:
        """WebSocket endpoint URL."""
        return f"ws://{self._host}:{self._port}"

    def connect(self) -> None:
        """Connect to the Photoshop UXP WebSocket server.

        Raises:
            BridgeConnectionError: If connection fails.
        """
        # TODO: Implement actual websockets connection
        # import websockets, asyncio
        # self._ws = asyncio.get_event_loop().run_until_complete(
        #     websockets.connect(self.endpoint, ping_interval=None)
        # )
        logger.info("PhotoshopBridge: connecting to %s (TODO: implement)", self.endpoint)
        self._connected = True

    def disconnect(self) -> None:
        """Disconnect from the UXP WebSocket."""
        if self._ws is not None:
            # TODO: close websocket
            self._ws = None
        self._connected = False
        logger.info("PhotoshopBridge: disconnected")

    def is_connected(self) -> bool:
        """Return True if the bridge is connected."""
        return self._connected

    def call(self, method: str, **params: Any) -> Any:
        """Call a UXP plugin method and return the result.

        Args:
            method: JSON-RPC method name (e.g. "ps.executeScript").
            **params: Method parameters.

        Returns:
            The result from Photoshop.

        Raises:
            BridgeConnectionError: If not connected.
            BridgeTimeoutError: If the call times out.
            RuntimeError: If the UXP plugin returns an error.
        """
        if not self._connected:
            raise BridgeConnectionError(
                f"Not connected to Photoshop UXP bridge at {self.endpoint}. "
                "Ensure Photoshop is running with the dcc-mcp UXP plugin installed."
            )

        with self._lock:
            self._request_id += 1
            _request = {
                "jsonrpc": "2.0",
                "id": self._request_id,
                "method": method,
                "params": params,
            }

        # TODO: send via websocket and await response
        # For now, raise NotImplementedError to signal placeholder
        raise NotImplementedError(
            f"PhotoshopBridge.call({method!r}) — WebSocket implementation pending. "
            "See bridge/uxp-plugin/ for the UXP plugin source."
        )

    def execute_script(self, code: str) -> Any:
        """Execute a JavaScript code snippet in Photoshop.

        Args:
            code: JavaScript/UXP code to execute.

        Returns:
            The return value of the script.
        """
        return self.call("ps.executeScript", code=code)

    def get_document_info(self) -> Dict[str, Any]:
        """Get information about the active Photoshop document."""
        return self.call("ps.getDocumentInfo")

    def __enter__(self) -> "PhotoshopBridge":
        self.connect()
        return self

    def __exit__(self, *args: Any) -> None:
        self.disconnect()
