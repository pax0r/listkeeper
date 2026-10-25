"""Resource consistency and domain boundaries, independent of Home Assistant."""

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "pax0r_listkeeper"


def test_manifest_domain_matches_directory():
    manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["domain"] == COMPONENT.name


def test_json_resources_are_parseable():
    for path in [*COMPONENT.rglob("*.json"), ROOT / "hacs.json", ROOT / "package.json"]:
        json.loads(path.read_text(encoding="utf-8"))


def test_domain_does_not_depend_on_infrastructure():
    for path in (COMPONENT / "domain").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            imports = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else []
            )
            assert not any(
                name.split(".")[0] in {"sqlalchemy", "homeassistant", "alembic"} for name in imports
            ), f"Domain boundary violation: {path}"
