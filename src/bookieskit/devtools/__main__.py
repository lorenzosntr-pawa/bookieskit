"""Entrypoint: python -m bookieskit.devtools <cmd>."""

import sys

from bookieskit.devtools.cli import main


def _force_utf8_output() -> None:
    """Make stdout/stderr UTF-8 so non-ASCII output (e.g. CHANGELOG arrows)
    doesn't crash on a Windows cp1252 console. No-op where unavailable."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass


if __name__ == "__main__":
    _force_utf8_output()
    sys.exit(main())
