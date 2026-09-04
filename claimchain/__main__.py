"""Command-line entry point: run claimchain via ``python -m claimchain``.

Delegates to :func:`claimchain.cli.main` so the module form behaves exactly
like the ``claimchain`` console script installed by ``pip``.
"""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
