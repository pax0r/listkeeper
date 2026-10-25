"""Provision integration packages without replacing Recorder's SQLAlchemy."""

import json
import subprocess
from importlib.metadata import version
from pathlib import Path

directory = Path(__file__).parent
requirements = json.loads((directory / "manifest.json").read_text())["requirements"]
constraints = directory / "constraints.txt"
constraints.write_text(f"SQLAlchemy=={version('SQLAlchemy')}\n", encoding="utf-8")
subprocess.run(
    ["uv", "pip", "install", "--system", "--constraint", str(constraints), *requirements],
    check=True,
)
