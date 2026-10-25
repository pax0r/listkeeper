"""Validation library boundary during HA's voluptuous/probatio transition."""

try:
    import probatio as vol
except ImportError:
    import voluptuous as vol

__all__ = ["vol"]
