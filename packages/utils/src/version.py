"""Authoritative package version access.

The installed distribution metadata is generated directly from ``pyproject.toml``.
All runtime surfaces use this helper instead of carrying independent literals.
"""

from importlib.metadata import PackageNotFoundError, version


def public_version() -> str:
    """Return the PEP 440 version in the UI's SemVer-compatible spelling."""
    try:
        value = version("driftguardx")
    except PackageNotFoundError:
        return "0.0.0+uninstalled"
    return value.replace("rc", "-rc")


APP_VERSION = public_version()
