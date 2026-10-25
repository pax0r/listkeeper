"""A responsive onboarding endpoint signals HTTP readiness before first login."""

from urllib.error import HTTPError, URLError
from urllib.request import urlopen

try:
    with urlopen("http://127.0.0.1:8123/api/onboarding", timeout=3) as response:
        ready = response.status == 200
except HTTPError as error:
    ready = error.code == 404  # Onboarding endpoint may disappear after completion.
except URLError, TimeoutError:
    ready = False
raise SystemExit(0 if ready else 1)
