"""Entrypoint: python -m bookieskit.devtools <cmd>."""

import sys

from bookieskit.devtools.cli import main

if __name__ == "__main__":
    sys.exit(main())
