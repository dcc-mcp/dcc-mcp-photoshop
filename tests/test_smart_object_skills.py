"""Regression checks for smart-object skill layer lookup."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPTS = Path(__file__).parent.parent / "src" / "dcc_mcp_photoshop" / "skills" / "photoshop-smart-object" / "scripts"


def _load_script(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / name)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


class _Layer:
    name = "Active layer"

    def __init__(self) -> None:
        self.smart_object = _SmartObject(self)


class _SmartObject:
    def __init__(self, layer: _Layer) -> None:
        self.layer = layer

    def convert_to_smart_object(self) -> _Layer:
        return self.layer

    def new_smart_object_via_copy(self) -> _Layer:
        return self.layer

    def edit_contents(self) -> None:
        return None

    def replace_contents(self, path: str) -> None:
        self.path = path


class _Photoshop:
    activeDocument = object()

    def __init__(self) -> None:
        self.activeLayer = _Layer()


@pytest.mark.parametrize(
    ("script", "function", "args", "expected"),
    [
        ("convert_to_smart_object.py", "_convert_to_smart_object", (), {"converted": True}),
        ("new_smart_object_via_copy.py", "_new_smart_object_via_copy", (), {"copied": True}),
        ("edit_smart_object_contents.py", "_edit_smart_object_contents", (), {"editing": True}),
        ("replace_smart_object_contents.py", "_replace_smart_object_contents", ("image.jpg",), {"replaced": True}),
    ],
)
def test_smart_object_tools_use_application_active_layer(script, function, args, expected):
    result = getattr(_load_script(script), function)(_Photoshop(), *args)

    assert result.items() >= expected.items()
    assert result["layer_name"] == "Active layer"
