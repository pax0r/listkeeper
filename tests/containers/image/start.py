"""Initialize only our fresh test volume and exec Home Assistant as PID 1."""

import os
import sys
from pathlib import Path

directory = Path("/config")
configuration = directory / "configuration.yaml"
if not configuration.exists():
    configuration.write_text(
        """homeassistant:
  name: Listkeeper container tests
  latitude: 52.23
  longitude: 21.01
  elevation: 100
  unit_system: metric
  country: PL
  time_zone: Europe/Warsaw
http:
api:
frontend:
config:
onboarding:
recorder:
  db_url: sqlite:////config/recorder.db
logger:
  default: warning
""",
        encoding="utf-8",
    )
os.execv(sys.executable, [sys.executable, "-m", "homeassistant", "--config", str(directory)])
