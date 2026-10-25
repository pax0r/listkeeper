"""Guarded Recorder configuration detection; never expose connection secrets."""

from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


def recorder_url(hass) -> str | None:
    """Recorder's db_url is implementation detail, isolated and optional."""
    try:
        from homeassistant.helpers.recorder import get_instance

        value = getattr(get_instance(hass), "db_url", None)
        if isinstance(value, str) and make_url(value).get_backend_name() in {
            "sqlite",
            "mysql",
            "mariadb",
            "postgresql",
        }:
            return value
    except ImportError, AttributeError, KeyError, ValueError, ArgumentError:
        pass
    return None


def database_url(hass, manual: str = "") -> str:
    detected = recorder_url(hass)
    selected = manual or detected
    if not selected:
        return "sqlite:///" + hass.config.path("pax0r_listkeeper.db")
    parsed = make_url(selected)
    backend = parsed.get_backend_name()
    if backend == "sqlite":
        # A single fixed owned SQLite file prevents touching Recorder, including
        # via a manually supplied path, symlink or SQLite URI query parameters.
        owned = Path(hass.config.path("pax0r_listkeeper.db")).resolve()
        if detected and make_url(detected).get_backend_name() == "sqlite":
            recorder_path = make_url(detected).database
            if recorder_path and Path(recorder_path).resolve() == owned:
                raise ValueError("Recorder already uses the integration database file")
        return "sqlite:///" + str(owned)
    if backend in {"mysql", "mariadb"}:
        parsed = parsed.set(drivername="mysql+pymysql")
    elif backend == "postgresql":
        parsed = parsed.set(drivername="postgresql+psycopg2")
    else:
        raise ValueError("Supported databases: SQLite, PostgreSQL, MariaDB and MySQL")
    return parsed.render_as_string(hide_password=False)
