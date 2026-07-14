"""Continuously reflect the live Photoshop bridge session in readiness."""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Dict

from dcc_mcp_photoshop.runtime_probe import probe_broker

logger = logging.getLogger(__name__)

BridgeProbe = Callable[[str, float], Dict[str, Any]]
BridgeStateCallback = Callable[[bool, Dict[str, Any]], None]


class BridgeSessionWatchdog:
    """Poll broker health and notify only when bridge availability changes."""

    def __init__(
        self,
        *,
        broker_url: str,
        timeout: float,
        poll_interval: float,
        on_state_change: BridgeStateCallback,
        probe: BridgeProbe = probe_broker,
    ) -> None:
        self._broker_url = broker_url
        self._timeout = max(0.1, float(timeout))
        self._poll_interval = max(0.1, float(poll_interval))
        self._on_state_change = on_state_change
        self._probe = probe
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_ready: bool | None = None

    @property
    def is_running(self) -> bool:
        """Return whether the watchdog thread is alive."""
        return bool(self._thread and self._thread.is_alive())

    def sample(self) -> bool:
        """Probe once, publish a transition if needed, and return readiness."""
        payload = self._probe(self._broker_url, self._timeout)
        ready = bool(payload.get("ok") and int(payload.get("sessions", 0)) > 0)
        if ready != self._last_ready:
            self._last_ready = ready
            self._on_state_change(ready, payload)
        return ready

    def start(self) -> None:
        """Start one daemon polling thread."""
        if self.is_running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="photoshop-bridge-watchdog",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Stop polling without blocking server shutdown indefinitely."""
        self._stop_event.set()
        thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=max(0.0, timeout))
        self._thread = None

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.sample()
            except Exception:  # noqa: BLE001 - watchdog must survive probe bugs
                logger.exception("Photoshop bridge watchdog sample failed")
            self._stop_event.wait(self._poll_interval)
