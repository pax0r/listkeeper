"""Collect logs and remove an interrupted, explicitly marked HA test stack."""

import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("project")
options = parser.parse_args()
if not re.fullmatch(r"listkeeper-test(?:-[a-z0-9-]+)?", options.project):
    parser.error("Only Listkeeper test project names are allowed")
compose = ["docker", "compose", "-f", str(ROOT / "compose.ha-test.yml"), "-p", options.project]
identities = subprocess.check_output(compose + ["ps", "--all", "--quiet"], text=True).split()
for identity in identities:
    metadata = json.loads(subprocess.check_output(["docker", "inspect", identity]))[0]
    labels = metadata["Config"]["Labels"]
    if (
        labels.get("io.pax0r.listkeeper.test-instance") != "true"
        or labels.get("com.docker.compose.project") != options.project
    ):
        parser.error("Refusing to remove a container not owned by this test stack")
results = ROOT / "test-results" / options.project
results.mkdir(parents=True, exist_ok=True)
with (results / "homeassistant.log").open("w", encoding="utf-8") as output:
    subprocess.run(
        compose + ["logs", "--no-color", "--timestamps", "homeassistant"],
        stdout=output,
        stderr=subprocess.STDOUT,
        check=True,
    )
subprocess.run(compose + ["down", "--volumes", "--remove-orphans"], check=True)
