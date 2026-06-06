#!/usr/bin/env python
"""Write all migration files for dcc-mcp-photoshop → adobepy migration."""
import os, sys

ROOT = r"F:\github\adobe-python-interpreter\dcc-mcp-photoshop"
SRC = os.path.join(ROOT, "src", "dcc_mcp_photoshop")
SKILLS = os.path.join(SRC, "skills")
TESTS = os.path.join(ROOT, "tests")

def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print(f"  OK: {os.path.relpath(path, ROOT)}")

# ==================== CORE FILES ====================

# api.py
write(os.path.join(SRC, "api.py"), open("api_migrated.py", encoding="utf-8").read())

# __init__.py
write(os.path.join(SRC, "__init__.py"), open("init_migrated.py", encoding="utf-8").read())

# ==================== ALL 16 SKILL SCRIPTS ====================
SKILL_FILES = {
    "photoshop-document/scripts/get_document_info.py": "skills_migrated/get_document_info.py",
    "photoshop-document/scripts/list_layers.py": "skills_migrated/list_layers.py",
    "photoshop-image/scripts/create_document.py": "skills_migrated/create_document.py",
    "photoshop-image/scripts/export_document.py": "skills_migrated/export_document.py",
    "photoshop-image/scripts/save_document.py": "skills_migrated/save_document.py",
    "photoshop-image/scripts/resize_canvas.py": "skills_migrated/resize_canvas.py",
    "photoshop-image/scripts/resize_image.py": "skills_migrated/resize_image.py",
    "photoshop-image/scripts/flatten_image.py": "skills_migrated/flatten_image.py",
    "photoshop-image/scripts/merge_visible_layers.py": "skills_migrated/merge_visible_layers.py",
    "photoshop-layers/scripts/create_layer.py": "skills_migrated/create_layer.py",
    "photoshop-layers/scripts/delete_layer.py": "skills_migrated/delete_layer.py",
    "photoshop-layers/scripts/duplicate_layer.py": "skills_migrated/duplicate_layer.py",
    "photoshop-layers/scripts/fill_layer.py": "skills_migrated/fill_layer.py",
    "photoshop-layers/scripts/rename_layer.py": "skills_migrated/rename_layer.py",
    "photoshop-layers/scripts/set_layer_blend_mode.py": "skills_migrated/set_layer_blend_mode.py",
    "photoshop-layers/scripts/set_layer_opacity.py": "skills_migrated/set_layer_opacity.py",
    "photoshop-layers/scripts/set_layer_visibility.py": "skills_migrated/set_layer_visibility.py",
    "photoshop-text/scripts/create_text_layer.py": "skills_migrated/create_text_layer.py",
    "photoshop-text/scripts/get_text_layer_info.py": "skills_migrated/get_text_layer_info.py",
    "photoshop-text/scripts/update_text_layer.py": "skills_migrated/update_text_layer.py",
}

for dest_rel, src_rel in SKILL_FILES.items():
    src_path = os.path.join(ROOT, src_rel)
    dest_path = os.path.join(SKILLS, dest_rel)
    write(dest_path, open(src_path, encoding="utf-8").read())

# ==================== TEST FILES ====================
write(os.path.join(TESTS, "conftest.py"), open("conftest_migrated.py", encoding="utf-8").read())
write(os.path.join(TESTS, "test_skills.py"), open("test_skills_migrated.py", encoding="utf-8").read())

# ==================== pyproject.toml ====================
# Already has adobepy dep - verify
import tomllib
with open(os.path.join(ROOT, "pyproject.toml"), "rb") as f:
    cfg = tomllib.load(f)
deps = cfg.get("project", {}).get("dependencies", [])
if not any("adobepy" in d for d in deps):
    print("  WARN: adobepy dependency missing from pyproject.toml!")

print("\nAll files written successfully!")
