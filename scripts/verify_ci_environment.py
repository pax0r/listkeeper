"""Reproduce CI dependency installation in a clean Linux container and virtualenv."""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def execute(*arguments: str) -> None:
    subprocess.run(list(arguments), check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inside-container", action="store_true")
    parser.add_argument("--ha", action="store_true", help="Install and run in-process HA tests")
    parser.add_argument("--update-lock", action="store_true", help="Explicitly regenerate uv.lock")
    arguments = parser.parse_args()
    if not arguments.inside_container:
        root = Path(__file__).resolve().parents[1]
        command = [
            "docker",
            "run",
            "--rm",
            "--label",
            "io.pax0r.listkeeper.ci-environment=true",
            "--mount",
            f"type=bind,source={root},target=/workspace",
            "--workdir",
            "/workspace",
            "--env",
            "UV_PROJECT_ENVIRONMENT=/tmp/listkeeper-ci-venv",
            "--env",
            "UV_CACHE_DIR=/tmp/listkeeper-ci-cache",
            "python:3.14.9-slim",
            "python",
            "scripts/verify_ci_environment.py",
            "--inside-container",
        ]
        if arguments.ha:
            command.append("--ha")
        if arguments.update_lock:
            command.append("--update-lock")
        execute(*command)
        return

    if (
        sys.platform != "linux"
        or os.environ.get("UV_PROJECT_ENVIRONMENT") != "/tmp/listkeeper-ci-venv"
    ):
        raise RuntimeError("The inner command requires the isolated Linux test environment")
    execute(sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "uv==0.13.5")
    lock_arguments = [] if arguments.update_lock else ["--check"]
    execute("uv", "lock", *lock_arguments, "--python", sys.executable)
    groups = ["--group", "dev", "--group", "ha" if arguments.ha else "container"]
    execute("uv", "sync", "--locked", "--python", sys.executable, *groups)
    execute("uv", "run", "--no-sync", "python", "--version")
    if arguments.ha:
        execute("uv", "run", "--no-sync", "pytest", "tests/ha", "-q", "-p", "no:cacheprovider")
    else:
        execute("uv", "run", "--no-sync", "ruff", "check", "custom_components", "tests", "scripts")
        execute(
            "uv",
            "run",
            "--no-sync",
            "ruff",
            "format",
            "--check",
            "custom_components",
            "tests",
            "scripts",
        )
        execute(
            "uv",
            "run",
            "--no-sync",
            "pytest",
            "--ignore=tests/ha",
            "--ignore=tests/containers",
            "-q",
            "-p",
            "no:cacheprovider",
        )


if __name__ == "__main__":
    main()
