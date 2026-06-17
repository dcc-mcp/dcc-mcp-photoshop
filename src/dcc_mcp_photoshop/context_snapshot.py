"""Context snapshot provider for Photoshop.

Collects Photoshop session state for gateway metadata aggregation.
When the broker is reachable, queries the active document info;
otherwise returns minimal availability data.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class PhotoshopContextSnapshotProvider:
    """Collect Photoshop session context for gateway metadata.

    The snapshot includes:
    - Photoshop version (from broker capabilities)
    - Active document name / path
    - Document dimensions and color mode
    - Layer count
    - Broker connection status

    All queries are best-effort — failures are logged but never raised.
    """

    def __init__(self) -> None:
        self._cached_version: Optional[str] = None
        self._cached_broker_url: Optional[str] = None

    def collect(self, broker_url: Optional[str] = None) -> dict[str, Any]:
        """Collect the current Photoshop context snapshot.

        Args:
            broker_url: adobepy broker URL (optional, for caching)

        Returns:
            Dict with keys: ``dcc_type``, ``version``, ``broker_available``,
            ``active_document``, ``layer_count``, ``error`` (if any).
        """
        snapshot: dict[str, Any] = {
            "dcc_type": "photoshop",
            "broker_available": False,
        }

        try:
            from adobe.core.client import BrokerClient  # noqa: PLC0415

            client = BrokerClient(
                broker_url=broker_url or "http://127.0.0.1:47391",
                token="dev-token",
                timeout=5.0,
            )

            # Get capabilities for version info
            caps = client.capabilities()
            version = caps.get("target", caps.get("version", "unknown"))
            snapshot["version"] = version
            snapshot["broker_available"] = True
            self._cached_version = version
            self._cached_broker_url = broker_url

            # Try to get active document info
            try:
                doc = client.call("photoshop", "document", "getActive")
                if doc:
                    snapshot["active_document"] = {
                        "name": doc.get("name", "Unknown"),
                        "width": doc.get("width"),
                        "height": doc.get("height"),
                        "mode": doc.get("mode", doc.get("colorMode")),
                    }

                    # Try to get layer count
                    try:
                        layers = client.call("photoshop", "document", "getLayers")
                        snapshot["layer_count"] = len(layers) if layers else 0
                    except Exception:
                        snapshot["layer_count"] = 0

            except Exception as exc:  # noqa: BLE001
                snapshot["active_document"] = None
                snapshot["layer_count"] = 0
                logger.debug("Could not query active document: %s", exc)

        except ImportError:
            snapshot["version"] = self._cached_version or "unknown"
            snapshot["error"] = "adobepy not installed"
            logger.debug("adobepy not available for context snapshot")
        except Exception as exc:  # noqa: BLE001
            snapshot["version"] = self._cached_version or "unknown"
            snapshot["error"] = str(exc)
            logger.debug("Context snapshot collection failed: %s", exc)

        return snapshot

    def collect_gateway_metadata(self, broker_url: Optional[str] = None) -> dict[str, Any]:
        """Collect metadata suitable for gateway registration.

        Returns a subset of the full snapshot optimized for gateway
        aggregation (version, broker status, document count).
        """
        snapshot = self.collect(broker_url=broker_url)
        return {
            "dcc_type": snapshot["dcc_type"],
            "version": snapshot.get("version", "unknown"),
            "broker_available": snapshot["broker_available"],
            "active_document": snapshot.get("active_document", {}).get("name")
            if snapshot.get("active_document")
            else None,
        }
