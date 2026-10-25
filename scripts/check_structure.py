"""Check packaging, parsable resources and architecture boundaries without HA."""

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "pax0r_listkeeper"


def main() -> None:
    manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
    if manifest["domain"] != COMPONENT.name:
        raise ValueError("Manifest domain must match integration directory")
    for path in [*COMPONENT.rglob("*.json"), ROOT / "hacs.json", ROOT / "package.json"]:
        json.loads(path.read_text(encoding="utf-8"))
    for path in (COMPONENT / "domain").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            imports = (
                [n.name for n in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else []
            )
            if any(
                name.split(".")[0] in {"sqlalchemy", "homeassistant", "alembic"} for name in imports
            ):
                raise ValueError(f"Domain boundary violation: {path}")
    print("Packaging, JSON and domain boundaries: OK")


if __name__ == "__main__":
    main()
