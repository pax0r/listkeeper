"""Run only the repository-owned HA stack; retain sanitized CI diagnostics."""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="ghcr.io/home-assistant/home-assistant:stable")
    parser.add_argument("--project", default="listkeeper-test")
    parser.add_argument("--port", type=int, default=8124)
    parser.add_argument("--keep", action="store_true", help="Keep the stack for inspection")
    options = parser.parse_args()
    if not 1 <= options.port <= 65535:
        parser.error("Port must be between 1 and 65535")
    if not re.fullmatch(r"listkeeper-test(?:-[a-z0-9-]+)?", options.project):
        parser.error("Project must be listkeeper-test or start with listkeeper-test-")
    results = ROOT / "test-results" / options.project
    results.mkdir(parents=True, exist_ok=True)
    environment = {**os.environ, "HA_TEST_IMAGE": options.image, "HA_TEST_PORT": str(options.port)}
    compose = ["docker", "compose", "-f", str(ROOT / "compose.ha-test.yml"), "-p", options.project]

    def command(arguments, **kwargs):
        return subprocess.run(arguments, cwd=ROOT, env=environment, check=True, **kwargs)

    # Never run onboarding against a previously used test volume by accident.
    try:
        command(["docker", "info"], stdout=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        print("Docker Engine is unavailable. Start Docker with Linux containers.", file=sys.stderr)
        return 2
    existing = command(compose + ["ps", "--all", "--quiet"], capture_output=True, text=True)
    volumes = command(
        [
            "docker",
            "volume",
            "ls",
            "-q",
            "--filter",
            f"label=com.docker.compose.project={options.project}",
        ],
        capture_output=True,
        text=True,
    )
    if existing.stdout.strip() or volumes.stdout.strip():
        parser.error("Project already has containers or volumes. Use a new --project name.")
    exit_code = 1
    try:
        command(compose + ["build", "--pull"])
        command(compose + ["up", "--detach", "--wait", "--wait-timeout", "600"])
        container = command(
            compose + ["ps", "--quiet", "homeassistant"], capture_output=True, text=True
        ).stdout.strip()
        metadata = command(["docker", "inspect", container], capture_output=True, text=True)
        inspected = json.loads(metadata.stdout)[0]
        (results / "image.json").write_text(
            json.dumps(
                {
                    "requested": options.image,
                    "image_id": inspected["Image"],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        test_environment = {
            **environment,
            "LISTKEEPER_CONTAINER_TEST": "1",
            "LISTKEEPER_COMPOSE_PROJECT": options.project,
        }
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/containers",
                "-q",
                "--tb=short",
                "-p",
                "no:cacheprovider",
                f"--junitxml={results / 'junit.xml'}",
            ],
            cwd=ROOT,
            env=test_environment,
            check=False,
        )
        exit_code = completed.returncode
    except subprocess.CalledProcessError as error:
        print(f"Container command failed (exit {error.returncode})", file=sys.stderr)
    finally:
        with (results / "homeassistant.log").open("w", encoding="utf-8") as output:
            subprocess.run(
                compose + ["logs", "--no-color", "--timestamps", "homeassistant"],
                cwd=ROOT,
                env=environment,
                stdout=output,
                stderr=subprocess.STDOUT,
                check=False,
            )
        if not options.keep:
            # Compose removes only resources belonging to this verified fresh project.
            completed = subprocess.run(
                compose + ["down", "--volumes", "--remove-orphans"],
                cwd=ROOT,
                env=environment,
                check=False,
            )
            if completed.returncode:
                exit_code = completed.returncode
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
