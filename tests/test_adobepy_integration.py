"""Acceptance tests for adobepy integration in dcc-mcp-photoshop.

Validates the end-to-end call chain: skill code -> adobepy facade -> broker
client -> mock result.  Each legacy ``ps.*`` method is mapped to its adobepy
replacement per the method map contract.

These tests are the merge gate for PIP-596 (dcc-mcp-photoshop first adobepy
integration PR).  They pass without Photoshop, a broker process, or a UXP bridge.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any, Dict, List, Optional

import pytest

# ---------------------------------------------------------------------------
# FakeClient — simulates the adobepy broker
# ---------------------------------------------------------------------------


class FakeClient:
    """Minimal BrokerClient that returns realistic Photoshop-shaped data.

    The call signature matches ``adobe.core.client.BrokerClient.call(...)``:
    ``call(host, namespace, method, args=None, options=None, target=None)``.
    """

    target = "default"

    def __init__(self, fail: Optional[BaseException] = None) -> None:
        self.fail = fail
        self.calls: List[Dict[str, Any]] = []

    # -- BrokerClient surface -------------------------------------------------

    def call(
        self,
        host: str,
        namespace: str,
        method: str,
        args: Optional[List[Any]] = None,
        options: Optional[Dict[str, Any]] = None,
        target: Optional[str] = None,
    ) -> Any:
        self.calls.append(
            {
                "host": host,
                "namespace": namespace,
                "method": method,
                "args": list(args or []),
                "options": options or {},
                "target": target,
            }
        )
        if self.fail is not None:
            raise self.fail

        handler = getattr(self, f"_handle_{namespace}", None)
        if handler is not None:
            return handler(method, list(args or []))
        return {"ok": True}

    def capabilities(self) -> list[dict[str, Any]]:
        """Return broker session list consumed by normalize_capability_sessions."""
        return [
            {
                "target": "default",
                "connectedAtEpochMs": 1718236800000,
                "capabilities": {
                    "host": "photoshop",
                    "bridgeKind": "uxp",
                    "bridgeVersion": "0.1.0",
                    "hostVersion": "25.0",
                    "namespaces": [
                        "app", "document", "layer", "text", "export",
                        "selection", "channel", "filter", "action", "raw",
                    ],
                    "features": ["snapshot", "modal", "selection", "batchPlay"],
                    "methods": {
                        "app": ("getVersion", "getDocuments"),
                        "document": ("getActive", "getById", "getLayers", "getActiveLayers",
                                      "export", "saveAs"),
                        "layer": ("getActive", "getChildren"),
                        "text": ("getActive", "getByLayerId", "setContents",
                                 "setCharacterStyle", "setParagraphStyle",
                                 "resetCharacterStyle", "setTextClickPoint",
                                 "setOrientation", "convertToParagraphText",
                                 "convertToPointText", "convertToShape", "createWorkPath"),
                        "export": ("getPresets", "exportWithPreset"),
                        "selection": ("get", "selectAll", "deselect", "inverse",
                                      "selectRectangle", "selectEllipse",
                                      "selectPolygon", "selectRow", "selectColumn",
                                      "expand", "contract", "feather", "smooth",
                                      "grow", "translateBoundary", "save"),
                        "channel": ("getChannels", "getActiveChannels",
                                    "getComponentChannels", "getByName", "remove"),
                        "filter": ("apply", "applyGaussianBlur", "applyHighPass",
                                   "applySharpen", "applySmartBlur"),
                        "action": ("batchPlay",),
                        "raw": ("evalJs", "evalExtendScript", "getPath", "callPath",
                                "sendSdkMessage"),
                    },
                },
            }
        ]

    # ------------------------------------------------------------------
    # app namespace
    # ------------------------------------------------------------------

    @staticmethod
    def _handle_app(method: str, _args: List[Any]) -> Any:
        if method == "getVersion":
            return "25.0"
        if method == "getDocuments":
            return [
                {"id": 1, "name": "Untitled-1.psd", "width": 1920, "height": 1080},
                {"id": 2, "name": "hero.psd", "width": 800, "height": 600},
            ]
        return {"ok": True}

    # ------------------------------------------------------------------
    # document namespace
    # ------------------------------------------------------------------

    @staticmethod
    def _handle_document(method: str, args: List[Any]) -> Any:
        if method == "getActive":
            return {
                "id": 1, "name": "Untitled-1.psd", "width": 1920, "height": 1080,
                "resolution": 72.0, "mode": "RGBColor", "bitDepth": 8,
                "path": None, "saved": True,
            }
        if method == "getById":
            return {
                "id": args[0], "name": "Untitled-1.psd", "width": 1920, "height": 1080,
                "resolution": 72.0,
            }
        if method == "getActiveLayers":
            # args[0] = document id (int)
            return [
                {"id": 11, "name": "Background", "kind": "pixel", "visible": True,
                 "opacity": 100},
                {"id": 12, "name": "Hero", "kind": "pixel", "visible": True,
                 "opacity": 75},
                {"id": 13, "name": "Hidden Layer", "kind": "pixel", "visible": False,
                 "opacity": 100},
            ]
        if method == "getLayers":
            return [
                {"id": 11, "name": "Background", "kind": "pixel", "visible": True},
                {"id": 12, "name": "Hero", "kind": "pixel", "visible": True},
            ]
        if method == "export":
            # args[0] = {"id":..., "path":..., "format":..., "options":..., "asCopy":...}
            payload = args[0] if args else {}
            return {"exported": True, "path": payload.get("path"), "format": payload.get("format", "png")}
        if method == "saveAs":
            payload = args[0] if args else {}
            return {"saved": True, "path": payload.get("path")}
        return {"ok": True}

    # ------------------------------------------------------------------
    # layer namespace
    # ------------------------------------------------------------------

    @staticmethod
    def _handle_layer(method: str, _args: List[Any]) -> Any:
        if method == "getActive":
            return {"id": 12, "name": "Hero", "kind": "text", "visible": True,
                    "opacity": 75}
        if method == "getChildren":
            return [
                {"id": 20, "name": "SubLayer1", "kind": "pixel", "visible": True,
                 "opacity": 100},
            ]
        return {"ok": True}

    # ------------------------------------------------------------------
    # text namespace
    # ------------------------------------------------------------------

    @staticmethod
    def _handle_text(method: str, args: List[Any]) -> Any:
        if method in ("getByLayerId", "getActive"):
            # Return payload whose layerId and characterStyle/paragraphStyle
            # keys match what TextItemProxy expects.
            return {
                "layerId": args[0] if args else 12,
                "contents": "Hello, World!",
                "characterStyle": {
                    "font": "ArialMT", "size": 48, "color": "#000000",
                    "bold": False, "italic": False, "tracking": 0,
                },
                "paragraphStyle": {"alignment": "left", "justification": "left"},
            }
        if method == "setContents":
            # args = [layer_id, contents]
            return {"layerId": args[0], "contents": args[1] if len(args) > 1 else ""}
        if method == "setCharacterStyle":
            # args = [layer_id, properties_dict]
            return {"layerId": args[0], "characterStyle": args[1] if len(args) > 1 else {}}
        if method == "setParagraphStyle":
            return {"layerId": args[0], "paragraphStyle": args[1] if len(args) > 1 else {}}
        if method == "setTextClickPoint":
            return {"layerId": args[0], "textClickPoint": args[1] if len(args) > 1 else {}}
        if method == "setOrientation":
            return {"layerId": args[0], "orientation": args[1] if len(args) > 1 else "horizontal"}
        if method in ("resetCharacterStyle", "convertToParagraphText",
                      "convertToPointText", "convertToShape", "createWorkPath"):
            return {"layerId": args[0]}
        return {"ok": True}

    # ------------------------------------------------------------------
    # channel namespace
    # ------------------------------------------------------------------

    @staticmethod
    def _handle_channel(method: str, _args: List[Any]) -> Any:
        if method == "getChannels":
            return [
                {"name": "Red", "kind": "channel", "visible": True, "opacity": 100},
                {"name": "Green", "kind": "channel", "visible": True, "opacity": 100},
                {"name": "Blue", "kind": "channel", "visible": True, "opacity": 100},
            ]
        if method == "getActiveChannels":
            return [
                {"name": "RGB", "kind": "composite", "visible": True, "opacity": 100},
            ]
        if method == "getComponentChannels":
            return [
                {"name": "Red", "kind": "channel", "visible": True},
                {"name": "Green", "kind": "channel", "visible": True},
                {"name": "Blue", "kind": "channel", "visible": True},
            ]
        if method == "getByName":
            name = _args[1] if len(_args) > 1 else "Red"
            return {"name": name, "kind": "channel", "visible": True, "opacity": 100}
        return {"ok": True}

    # ------------------------------------------------------------------
    # export namespace
    # ------------------------------------------------------------------

    @staticmethod
    def _handle_export(method: str, args: List[Any]) -> Any:
        if method == "getPresets":
            return [
                {"name": "png", "format": "png", "description": "PNG 24"},
                {"name": "jpg_high", "format": "jpg", "description": "JPEG High"},
            ]
        if method == "exportWithPreset":
            payload = args[0] if args else {}
            return {"exported": True, "path": payload.get("path"),
                    "preset": payload.get("preset")}
        return {"ok": True}

    # ------------------------------------------------------------------
    # selection namespace
    # ------------------------------------------------------------------

    @staticmethod
    def _handle_selection(method: str, args: List[Any]) -> Any:
        if method == "get":
            # args[0] = document_id
            return {"docId": args[0] if args else 1,
                    "bounds": {"top": 0, "left": 0, "bottom": 1080, "right": 1920},
                    "solid": True, "typename": "Selection"}
        if method == "selectRectangle":
            return {"bounds": args[1] if len(args) > 1 else {},
                    "docId": args[0] if args else 1}
        if method in ("selectAll", "deselect", "inverse", "selectRow",
                      "selectColumn", "selectEllipse", "selectPolygon",
                      "expand", "contract", "feather", "smooth", "grow",
                      "translateBoundary", "save"):
            return {"docId": args[0] if args else 1, "bounds": {}}
        return {"ok": True}

    # ------------------------------------------------------------------
    # filter namespace
    # ------------------------------------------------------------------

    @staticmethod
    def _handle_filter(method: str, args: List[Any]) -> Any:
        # Most filter methods: args = [layer_id, *method_args]
        if method == "apply":
            return {"id": args[0] if args else 12}
        if method in ("applyGaussianBlur", "applyHighPass"):
            return {"id": args[0] if args else 12, "radius": args[1] if len(args) > 1 else 1}
        if method == "applySharpen":
            return {"id": args[0] if args else 12}
        if method == "applySmartBlur":
            return {"id": args[0] if args else 12,
                    "radius": args[1] if len(args) > 1 else 1,
                    "threshold": args[2] if len(args) > 2 else 0}
        return {"ok": True}

    # ------------------------------------------------------------------
    # action namespace
    # ------------------------------------------------------------------

    @staticmethod
    def _handle_action(method: str, args: List[Any]) -> Any:
        if method == "batchPlay":
            return [{"_result": "ok"}]
        return {"ok": True}

    # ------------------------------------------------------------------
    # raw namespace
    # ------------------------------------------------------------------

    @staticmethod
    def _handle_raw(method: str, args: List[Any]) -> Any:
        if method == "evalJs":
            code = str(args[0]) if args else ""
            if code == "app.documents.length":
                return 1
            if code == "app.activeDocument.name":
                return "Untitled-1.psd"
            if code == "app.preferences.rulerUnits":
                return "Units.PIXELS"
            return f"raw_js:{code}"
        if method == "evalExtendScript":
            code = str(args[0]) if args else ""
            return f"raw_jsx:{code}"
        if method == "getPath":
            return {"typename": "Document", "name": "Untitled-1.psd"}
        if method == "callPath":
            return {"_result": "ok"}
        return {"ok": True}


# ---------------------------------------------------------------------------
# Helper: build a Photoshop session with the FakeClient
# ---------------------------------------------------------------------------


def _make_ps(client: Optional[FakeClient] = None) -> Photoshop:  # noqa: F821
    from adobe.photoshop import Photoshop

    return Photoshop(client=client or FakeClient())


# ---------------------------------------------------------------------------
# Document operations (ps.getDocumentInfo, ps.listDocuments)
# ---------------------------------------------------------------------------


class TestAdobepyDocumentIntegration:
    """Exercises the typed_facade route for document methods."""

    def test_active_document_returns_name_and_dimensions(self) -> None:
        app = _make_ps()
        doc = app.activeDocument
        assert doc is not None
        assert doc.name == "Untitled-1.psd"
        assert doc.width == 1920
        assert doc.height == 1080

    def test_active_document_pythonic_alias(self) -> None:
        app = _make_ps()
        doc = app.active_document
        assert doc is not None
        assert doc.name == "Untitled-1.psd"

    def test_list_documents(self) -> None:
        app = _make_ps()
        docs = app.documents
        assert len(docs) == 2
        assert docs[0].name == "Untitled-1.psd"
        assert docs[1].name == "hero.psd"

    def test_document_export_via_facade(self) -> None:
        client = FakeClient()
        app = _make_ps(client)
        doc = app.activeDocument
        assert doc is not None
        result = doc.export("/tmp/out.png", format="png")
        assert result["exported"] is True
        documented = client.calls[-1]
        assert documented["namespace"] == "document"
        assert documented["method"] == "export"

    def test_document_save_as(self) -> None:
        client = FakeClient()
        app = _make_ps(client)
        doc = app.activeDocument
        assert doc is not None
        result = doc.save_as("/tmp/out.psd", format="psd")
        assert result["saved"] is True
        documented = client.calls[-1]
        assert documented["namespace"] == "document"
        assert documented["method"] == "saveAs"

    def test_document_channels(self) -> None:
        app = _make_ps()
        doc = app.activeDocument
        assert doc is not None
        channels = list(doc.channels)
        assert len(channels) == 3
        names = {ch.name for ch in channels}
        assert "Red" in names
        assert "Green" in names
        assert "Blue" in names

    def test_document_resolution(self) -> None:
        app = _make_ps()
        doc = app.activeDocument
        assert doc is not None
        assert doc.resolution == 72.0


# ---------------------------------------------------------------------------
# Layer operations (ps.listLayers, ps.listLayers filtering)
# ---------------------------------------------------------------------------


class TestAdobepyLayerIntegration:
    """Exercises the typed_facade route for layer methods."""

    def test_active_layers_returns_all(self) -> None:
        app = _make_ps()
        layers = list(app.activeLayers)
        assert len(layers) == 3

    def test_active_layers_pythonic_alias(self) -> None:
        app = _make_ps()
        layers = list(app.active_layers)
        assert len(layers) == 3
        names = {lyr.name for lyr in layers}
        assert "Background" in names
        assert "Hero" in names
        assert "Hidden Layer" in names

    def test_active_layer_is_text_kind(self) -> None:
        app = _make_ps()
        layer = app.activeLayer
        assert layer is not None
        assert layer.name == "Hero"
        assert layer.kind == "text"

    def test_layer_opacity(self) -> None:
        app = _make_ps()
        layer = app.activeLayer
        assert layer is not None
        assert layer.opacity == 75

    def test_layer_visible_flag(self) -> None:
        app = _make_ps()
        layers = list(app.activeLayers)
        visible = {lyr.name: lyr.visible for lyr in layers}
        assert visible["Background"] is True
        assert visible["Hidden Layer"] is False

    def test_layer_visibility_filtering(self) -> None:
        """The broker returns all layers; filtering by visibility is done
        by the caller (skill layer), not by the facade."""
        app = _make_ps()
        layers = list(app.activeLayers)
        hidden = [lyr for lyr in layers if not lyr.visible]
        assert len(hidden) == 1
        assert hidden[0].name == "Hidden Layer"


# ---------------------------------------------------------------------------
# Text operations (ps.getTextLayerInfo, ps.updateTextLayer)
# ---------------------------------------------------------------------------


class TestAdobepyTextIntegration:
    """Exercises the typed_facade route for text methods."""

    def test_active_text_returns_content(self) -> None:
        app = _make_ps()
        text = app.activeText
        assert text is not None
        assert text.contents == "Hello, World!"

    def test_active_text_pythonic_alias(self) -> None:
        app = _make_ps()
        text = app.active_text
        assert text is not None
        assert text.contents == "Hello, World!"

    def test_text_set_contents(self) -> None:
        client = FakeClient()
        app = _make_ps(client)
        text = app.activeText
        assert text is not None
        result = text.set_contents("Updated from adobepy")
        assert result.contents == "Updated from adobepy"
        documented = client.calls[-1]
        assert documented["namespace"] == "text"
        assert documented["method"] == "setContents"

    def test_text_character_style_read(self) -> None:
        app = _make_ps()
        text = app.activeText
        assert text is not None
        assert text.character_style.font == "ArialMT"
        assert text.character_style.size == 48
        assert text.character_style.color == "#000000"

    def test_text_character_style_update(self) -> None:
        client = FakeClient()
        app = _make_ps(client)
        text = app.activeText
        assert text is not None
        text.character_style.update(size=72, tracking=10)
        documented = client.calls[-1]
        assert documented["namespace"] == "text"
        assert documented["method"] == "setCharacterStyle"

    def test_text_paragraph_style_update(self) -> None:
        client = FakeClient()
        app = _make_ps(client)
        text = app.activeText
        assert text is not None
        text.paragraph_style.update(justification="center")
        documented = client.calls[-1]
        assert documented["namespace"] == "text"
        assert documented["method"] == "setParagraphStyle"

    def test_text_orientation(self) -> None:
        client = FakeClient()
        app = _make_ps(client)
        text = app.activeText
        assert text is not None
        text.set_orientation("vertical")
        documented = client.calls[-1]
        assert documented["namespace"] == "text"
        assert documented["method"] == "setOrientation"


# ---------------------------------------------------------------------------
# Selection operations
# ---------------------------------------------------------------------------


class TestAdobepySelectionIntegration:
    """Exercises selection methods."""

    def test_selection_bounds_on_construction(self) -> None:
        """SelectionProxy.__init__ calls refresh(), which hits the broker."""
        app = _make_ps()
        doc = app.activeDocument
        assert doc is not None
        sel = doc.selection
        assert sel is not None
        assert sel.bounds is not None
        assert sel.bounds["top"] == 0

    def test_select_rectangle(self) -> None:
        client = FakeClient()
        app = _make_ps(client)
        doc = app.activeDocument
        assert doc is not None
        doc.selection.select_rectangle(
            {"top": 10, "left": 10, "bottom": 256, "right": 256}
        )
        documented = client.calls[-1]
        assert documented["namespace"] == "selection"
        assert documented["method"] == "selectRectangle"

    def test_select_all_and_deselect(self) -> None:
        client = FakeClient()
        app = _make_ps(client)
        doc = app.activeDocument
        assert doc is not None
        doc.selection.select_all()
        s1 = client.calls[-1]
        assert s1["method"] == "selectAll"
        doc.selection.deselect()
        s2 = client.calls[-1]
        assert s2["method"] == "deselect"


# ---------------------------------------------------------------------------
# Capabilities (capability_contract route)
# ---------------------------------------------------------------------------


class TestAdobepyCapabilitiesIntegration:
    """Exercises the broker capabilities surfaced through HostSession."""

    def test_capabilities_has_host(self) -> None:
        app = _make_ps()
        caps = app.capabilities()
        assert caps is not None
        assert caps.host == "photoshop"

    def test_capabilities_has_methods(self) -> None:
        app = _make_ps()
        caps = app.capabilities()
        assert caps is not None
        assert "document" in caps.methods
        assert "getActive" in caps.methods["document"]
        assert "setContents" in caps.methods["text"]

    def test_capabilities_bridge_kind(self) -> None:
        app = _make_ps()
        caps = app.capabilities()
        assert caps is not None
        assert caps.bridge_kind == "uxp"


# ---------------------------------------------------------------------------
# Raw evaluation (ps.executeScript → raw_eval route)
# ---------------------------------------------------------------------------


class TestAdobepyRawIntegration:
    """Exercises raw JavaScript and ExtendScript escape hatches."""

    def test_eval_js_returns_scalar(self) -> None:
        client = FakeClient()
        app = _make_ps(client)
        result = app.eval_js("app.documents.length")
        assert result == 1

    def test_eval_js_returns_string(self) -> None:
        client = FakeClient()
        app = _make_ps(client)
        result = app.eval_js("app.activeDocument.name")
        assert result == "Untitled-1.psd"

    def test_raw_namespace_eval_js(self) -> None:
        client = FakeClient()
        app = _make_ps(client)
        result = app.raw.eval_js("app.preferences.rulerUnits")
        assert result == "Units.PIXELS"

    def test_raw_namespace_eval_extendscript(self) -> None:
        client = FakeClient()
        app = _make_ps(client)
        result = app.raw.eval_extendscript("alert('hello');")
        assert "raw_jsx:alert" in str(result)

    def test_dom_proxy_get_path(self) -> None:
        app = _make_ps()
        doc = app.activeDocument
        assert doc is not None
        info = doc.dom.get()
        assert info["name"] == "Untitled-1.psd"


# ---------------------------------------------------------------------------
# BatchPlay operations (batch_play route)
# ---------------------------------------------------------------------------


class TestAdobepyBatchPlayIntegration:
    """Exercises the action namespace via batchPlay."""

    def test_batch_play_via_app(self) -> None:
        client = FakeClient()
        app = _make_ps(client)
        result = app.batch_play([{"_obj": "hide"}])
        assert result is not None
        documented = client.calls[-1]
        assert documented["namespace"] == "action"
        assert documented["method"] == "batchPlay"


# ---------------------------------------------------------------------------
# Export presets
# ---------------------------------------------------------------------------


class TestAdobepyExportPresetsIntegration:
    """Exercises export presets read path."""

    def test_export_presets_list(self) -> None:
        app = _make_ps()
        presets = app.exportPresets
        assert len(presets) == 2
        names = {p.name for p in presets}
        assert "png" in names
        assert "jpg_high" in names

    def test_export_with_preset(self) -> None:
        client = FakeClient()
        app = _make_ps(client)
        doc = app.activeDocument
        assert doc is not None
        result = doc.export_with_preset("png", "/tmp/out.png")
        assert result["exported"] is True
        documented = client.calls[-1]
        assert documented["namespace"] == "export"
        assert documented["method"] == "exportWithPreset"


# ---------------------------------------------------------------------------
# dcc_mcp helpers integration
# ---------------------------------------------------------------------------


class TestAdobepyDccMcpIntegration:
    """Exercises the adobe.dcc_mcp helpers with the Photoshop facade."""

    def test_action_result_with_typed_facade(self) -> None:
        from adobe.dcc_mcp import action_result
        from adobe.photoshop import Photoshop

        app = Photoshop(client=FakeClient())

        result = action_result(
            "Listed active Photoshop layers",
            lambda: {"layers": [lyr.name for lyr in app.activeLayers]},
            prompt="Use the layer names in the next Photoshop operation.",
        )
        assert result["success"] is True
        assert result["message"] == "Listed active Photoshop layers"
        assert result["context"]["layers"] == ["Background", "Hero", "Hidden Layer"]
        assert result["prompt"] == "Use the layer names in the next Photoshop operation."

    def test_adobe_success_helper(self) -> None:
        from adobe.dcc_mcp import adobe_success

        result = adobe_success("Done", count=5)
        assert result["success"] is True
        assert result["context"]["count"] == 5

    def test_adobe_error_helper(self) -> None:
        from adobe.dcc_mcp import adobe_error

        result = adobe_error("Failed", "ConnectionRefused")
        assert result["success"] is False
        assert result["error"] == "ConnectionRefused"

    def test_action_result_maps_exceptions(self) -> None:
        from adobe.core.errors import BrokerConnectionError
        from adobe.dcc_mcp import action_result
        from adobe.photoshop import Photoshop

        app = Photoshop(client=FakeClient(fail=BrokerConnectionError("broker down")))

        result = action_result("Listed layers", lambda: list(app.activeLayers))
        assert result["success"] is False
        assert result["context"]["adobepy"]["error_type"] == "BrokerConnectionError"
        assert result["context"]["adobepy"]["retryable"] is True

    def test_action_result_document_info_pattern(self) -> None:
        """Simulates the get_document_info skill pattern via adobepy."""
        from adobe.dcc_mcp import action_result
        from adobe.photoshop import Photoshop

        app = Photoshop(client=FakeClient())

        result = action_result(
            "Retrieved document info",
            lambda: {
                "document_name": app.activeDocument.name,
                "width": app.activeDocument.width,
                "height": app.activeDocument.height,
                "resolution": app.activeDocument.resolution,
            },
        )
        assert result["success"] is True
        assert result["context"]["document_name"] == "Untitled-1.psd"
        assert result["context"]["width"] == 1920

    def test_action_result_list_layers_pattern(self) -> None:
        """Simulates the list_layers skill pattern via adobepy."""
        from adobe.dcc_mcp import action_result
        from adobe.photoshop import Photoshop

        app = Photoshop(client=FakeClient())

        result = action_result(
            "Listed layers",
            lambda: {
                "count": len(list(app.activeLayers)),
                "layers": [lyr.name for lyr in app.activeLayers],
            },
        )
        assert result["success"] is True
        assert result["context"]["count"] == 3
        assert "Background" in result["context"]["layers"]

    def test_with_adobe_decorator_catches_errors(self) -> None:
        from adobe.core.errors import BrokerConnectionError
        from adobe.dcc_mcp import adobe_success, with_adobe
        from adobe.photoshop import Photoshop

        @with_adobe("Photoshop skill failed")
        def my_skill(**kwargs):
            app = Photoshop(client=FakeClient(fail=BrokerConnectionError("down")))
            return adobe_success("ok", layers=list(app.activeLayers))

        result = my_skill()
        assert result["success"] is False
        assert result["context"]["adobepy"]["error_type"] == "BrokerConnectionError"


# ---------------------------------------------------------------------------
# Bridge compatibility — legacy bridge-based skills still work
# ---------------------------------------------------------------------------


class TestAdobepySkillScriptIntegration:
    """Validate that skill scripts work end-to-end with a FakeClient.

    The skill scripts under ``skills/*/scripts/`` import ``Photoshop`` and
    ``action_result`` from adobepy directly.  These tests verify that when
    Photoshop is given a FakeClient the full call chain works — from skill
    entry point down through the facade to the broker mock.
    """

    @staticmethod
    def _load_script(scripts_dir: pathlib.Path, name: str):
        import importlib.util

        path = scripts_dir / name
        spec = importlib.util.spec_from_file_location(f"skill_{path.stem}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_get_document_info_skill(self) -> None:
        """get_document_info skill works with a FakeClient-injected Photoshop."""
        from unittest.mock import patch

        scripts_dir = (
            pathlib.Path(__file__).parent.parent
            / "src"
            / "dcc_mcp_photoshop"
            / "skills"
            / "photoshop-document"
            / "scripts"
        )
        app = _make_ps()

        with patch("adobe.photoshop.Photoshop", return_value=app):
            mod = self._load_script(scripts_dir, "get_document_info.py")
            result = mod.get_document_info()

        assert result["success"] is True
        assert result["context"]["document_name"] == "Untitled-1.psd"
        assert result["context"]["width"] == 1920
        assert result["context"]["height"] == 1080

    def test_list_layers_skill(self) -> None:
        """list_layers skill works with a FakeClient-injected Photoshop."""
        from unittest.mock import patch

        scripts_dir = (
            pathlib.Path(__file__).parent.parent
            / "src"
            / "dcc_mcp_photoshop"
            / "skills"
            / "photoshop-document"
            / "scripts"
        )
        app = _make_ps()

        with patch("adobe.photoshop.Photoshop", return_value=app):
            mod = self._load_script(scripts_dir, "list_layers.py")
            result = mod.list_layers()

        assert result["success"] is True
        assert result["context"]["count"] == 2  # document.layers has 2 items
        assert "Background" in result["context"]["layers"]

    def test_list_layers_with_hidden(self) -> None:
        """list_layers with include_hidden=False filters via Python, not broker."""
        from unittest.mock import patch

        scripts_dir = (
            pathlib.Path(__file__).parent.parent
            / "src"
            / "dcc_mcp_photoshop"
            / "skills"
            / "photoshop-document"
            / "scripts"
        )
        app = _make_ps()

        with patch("adobe.photoshop.Photoshop", return_value=app):
            mod = self._load_script(scripts_dir, "list_layers.py")
            result = mod.list_layers(include_hidden=False)

        assert result["success"] is True
        # document.layers returns 2 layers (Background, Hero) — neither is hidden
        assert result["context"]["count"] == 2
        assert "Hidden Layer" not in result["context"]["layers"]


class TestAdobepyBridgeCompatibility:
    """Validate that the existing bridge-based test infrastructure remains intact.

    These tests use the ``connected_bridge`` fixture which simulates a UXP
    WebSocket bridge.  The dcc_mcp_photoshop.api module-level ``_bridge``
    singleton is used by skills that haven't yet migrated to adobepy, so
    this path must keep working.
    """

    def test_connected_bridge_fixture_works(self, connected_bridge) -> None:
        """The conftest connected_bridge fixture still provides a working bridge."""
        import dcc_mcp_photoshop.api as api_mod
        from dcc_mcp_photoshop.api import is_photoshop_available

        api_mod._bridge = connected_bridge
        assert is_photoshop_available() is True

    def test_legacy_bridge_call_document_info(self, connected_bridge) -> None:
        """Legacy bridge.call('ps.getDocumentInfo') still returns mock data."""
        import dcc_mcp_photoshop.api as api_mod

        api_mod._bridge = connected_bridge

        from dcc_mcp_photoshop.api import get_bridge

        bridge = get_bridge()
        result = bridge.call("ps.getDocumentInfo")
        assert result["name"] == "Untitled-1.psd"
        assert result["width"] == 1920

    def test_legacy_bridge_call_list_layers(self, connected_bridge) -> None:
        """Legacy bridge.call('ps.listLayers') still returns mock layers."""
        import dcc_mcp_photoshop.api as api_mod

        api_mod._bridge = connected_bridge

        from dcc_mcp_photoshop.api import get_bridge

        bridge = get_bridge()
        result = bridge.call("ps.listLayers")
        assert len(result) == 3
        assert result[0]["name"] == "Background"


# ---------------------------------------------------------------------------
# Method map coverage — every legacy method has an adobepy equivalent
# ---------------------------------------------------------------------------


class TestAdobepyMethodMapCoverage:
    """Ensures every method in the method map contract is traversable via adobepy."""

    _METHOD_MAP: Optional[List[Dict[str, Any]]] = None

    @classmethod
    def _load_method_map(cls) -> List[Dict[str, Any]]:
        if cls._METHOD_MAP is None:
            # Primary path: contracts/ in the monorepo root
            contract_path = (
                pathlib.Path(__file__).parents[3]
                / "contracts"
                / "dcc_mcp_photoshop_methods.json"
            )
            # Fallback: relative to the dcc-mcp-photoshop checkout nested inside
            if not contract_path.exists():
                contract_path = (
                    pathlib.Path(__file__).parent.parent.parent
                    / "contracts"
                    / "dcc_mcp_photoshop_methods.json"
                )
            if contract_path.exists():
                cls._METHOD_MAP = json.loads(contract_path.read_text())["methods"]
            else:
                cls._METHOD_MAP = []
        return cls._METHOD_MAP

    def test_all_legacy_methods_have_adobepy_replacement(self) -> None:
        methods = self._load_method_map()
        if not methods:
            pytest.skip("method map contract not found")
        for entry in methods:
            assert entry.get("adobepy"), (
                f"{entry['legacyMethod']} has no adobepy replacement"
            )

    def test_method_count_matches_legacy_surface(self) -> None:
        """The contract covers all 27 legacy methods."""
        methods = self._load_method_map()
        if not methods:
            pytest.skip("method map contract not found")
        assert len(methods) == 27, (
            f"Expected 27 legacy methods, found {len(methods)}"
        )

    def test_each_legacy_method_has_valid_route(self) -> None:
        methods = self._load_method_map()
        if not methods:
            pytest.skip("method map contract not found")
        valid_routes = {
            "typed_facade", "batch_play", "dom_escape_hatch",
            "raw_eval", "capability_contract",
        }
        for entry in methods:
            assert entry["route"] in valid_routes, (
                f"{entry['legacyMethod']} has unknown route: {entry['route']}"
            )

    def test_method_map_json_has_all_required_keys(self) -> None:
        methods = self._load_method_map()
        if not methods:
            pytest.skip("method map contract not found")
        required = {"legacyMethod", "family", "route", "adobepy"}
        for entry in methods:
            missing = required - set(entry.keys())
            assert not missing, (
                f"{entry.get('legacyMethod', '?')} missing keys: {missing}"
            )

    def test_typed_facade_methods_are_present(self) -> None:
        methods = self._load_method_map()
        if not methods:
            pytest.skip("method map contract not found")
        facade_methods = {m["legacyMethod"] for m in methods if m["route"] == "typed_facade"}
        expected = {
            "ps.getDocumentInfo", "ps.listDocuments", "ps.exportDocument",
            "ps.listLayers", "ps.updateTextLayer", "ps.getTextLayerInfo",
        }
        missing = expected - facade_methods
        assert not missing, f"Expected typed_facade methods missing from contract: {missing}"
