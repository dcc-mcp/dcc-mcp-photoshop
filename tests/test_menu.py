"""Tests for dcc_mcp_photoshop._menu — unified menu actions."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from dcc_mcp_photoshop import __version__
from dcc_mcp_photoshop._menu import (
    copy_instance_id,
    format_about,
    format_server_info,
    resolve_instance_id,
    set_clipboard_text,
)

# ── resolve_instance_id ─────────────────────────────────────────────────
#
# resolve_instance_id imports dcc_mcp_photoshop.get_server locally, so we
# patch dcc_mcp_photoshop.get_server (the source module, not _menu).


class TestResolveInstanceId:
    def test_returns_none_when_no_server(self):
        with patch("dcc_mcp_photoshop.get_server", return_value=None):
            assert resolve_instance_id() is None

    def test_returns_instance_id_from_server(self):
        fake_server = SimpleNamespace(instance_id="test-uuid-1234")
        with patch("dcc_mcp_photoshop.get_server", return_value=fake_server):
            assert resolve_instance_id() == "test-uuid-1234"

    def test_falls_back_to_config_instance_id(self):
        fake_server = SimpleNamespace(
            instance_id=None,
            _config=SimpleNamespace(instance_id="config-uuid-5678"),
        )
        with patch("dcc_mcp_photoshop.get_server", return_value=fake_server):
            assert resolve_instance_id() == "config-uuid-5678"

    def test_strips_whitespace(self):
        fake_server = SimpleNamespace(instance_id="  whitespace-uuid  ")
        with patch("dcc_mcp_photoshop.get_server", return_value=fake_server):
            assert resolve_instance_id() == "whitespace-uuid"

    def test_returns_none_for_empty_string(self):
        fake_server = SimpleNamespace(instance_id="   ")
        with patch("dcc_mcp_photoshop.get_server", return_value=fake_server):
            assert resolve_instance_id() is None

    def test_survives_import_error(self):
        with patch("dcc_mcp_photoshop.get_server", side_effect=ImportError("no server")):
            # Should not raise — just return None
            assert resolve_instance_id() is None


# ── set_clipboard_text ─────────────────────────────────────────────────


class TestSetClipboardText:
    def test_raises_when_no_pyside_binding(self, monkeypatch):
        """Without PySide2 or PySide6, the function should raise RuntimeError."""
        original_import = __import__

        def fake_import(name, *args, **kwargs):
            if name in ("PySide2", "PySide6"):
                raise ImportError(f"No module named '{name}'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", fake_import)
        with pytest.raises(RuntimeError, match="no PySide binding"):
            set_clipboard_text("test")

    def test_uses_pyside2_when_available(self, monkeypatch):
        clipboard_texts = []

        class FakeClipboard:
            def setText(self, text):
                clipboard_texts.append(text)

        class FakeApp:
            @staticmethod
            def instance():
                return FakeApp()

            @staticmethod
            def clipboard():
                return FakeClipboard()

        class FakeQtWidgets:
            QApplication = FakeApp

        fake_mod = SimpleNamespace(QtWidgets=FakeQtWidgets)

        original_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "PySide2":
                return fake_mod
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", fake_import)
        set_clipboard_text("my-uuid")
        assert clipboard_texts == ["my-uuid"]

    def test_falls_back_to_pyside6(self, monkeypatch):
        clipboard_texts = []

        class FakeClipboard:
            def setText(self, text):
                clipboard_texts.append(text)

        class FakeApp:
            @staticmethod
            def instance():
                return FakeApp()

            @staticmethod
            def clipboard():
                return FakeClipboard()

        class FakeQtWidgets:
            QApplication = FakeApp

        fake_mod = SimpleNamespace(QtWidgets=FakeQtWidgets)

        original_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "PySide2":
                raise ImportError("No PySide2")
            if name == "PySide6":
                return fake_mod
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", fake_import)
        set_clipboard_text("pyside6-uuid")
        assert clipboard_texts == ["pyside6-uuid"]


# ── copy_instance_id ───────────────────────────────────────────────────


class TestCopyInstanceId:
    def test_raises_when_no_instance_id(self):
        with patch("dcc_mcp_photoshop._menu.resolve_instance_id", return_value=None):
            with pytest.raises(RuntimeError, match="Instance ID not available"):
                copy_instance_id()

    def test_returns_instance_id_on_success(self):
        with patch("dcc_mcp_photoshop._menu.resolve_instance_id", return_value="my-instance"):
            with patch("dcc_mcp_photoshop._menu.set_clipboard_text"):
                assert copy_instance_id() == "my-instance"


# ── format_server_info ─────────────────────────────────────────────────
#
# format_server_info also imports dcc_mcp_photoshop.get_server locally.


class TestFormatServerInfo:
    def test_includes_adapter_version(self):
        with patch("dcc_mcp_photoshop.get_server", return_value=None):
            info = format_server_info()
        assert f"Adapter Version: {__version__}" in info
        assert "Instance UUID:" in info
        assert "PID:" in info
        assert "Photoshop (via adobepy)" in info

    def test_includes_server_url_when_running(self):
        fake_server = SimpleNamespace(
            instance_id="running-uuid",
            mcp_url="http://127.0.0.1:18765/mcp",
        )
        with patch("dcc_mcp_photoshop.get_server", return_value=fake_server):
            info = format_server_info()
        assert "running-uuid" in info
        assert "http://127.0.0.1:18765/mcp" in info

    def test_shows_gateway_disabled_when_port_zero(self, monkeypatch):
        monkeypatch.setenv("DCC_MCP_GATEWAY_PORT", "0")
        with patch("dcc_mcp_photoshop.get_server", return_value=None):
            info = format_server_info()
        assert "Gateway Port: disabled" in info

    def test_shows_gateway_port(self, monkeypatch):
        monkeypatch.setenv("DCC_MCP_GATEWAY_PORT", "9765")
        with patch("dcc_mcp_photoshop.get_server", return_value=None):
            info = format_server_info()
        assert "Gateway Port: 9765" in info


# ── format_about ────────────────────────────────────────────────────────


class TestFormatAbout:
    def test_includes_version_and_repo_url(self):
        about = format_about()
        assert f"v{__version__}" in about
        assert "github.com/dcc-mcp/dcc-mcp-photoshop" in about
        assert f"Python {sys.version.split()[0]}" in about
        assert "AI-driven DCC automation" in about
