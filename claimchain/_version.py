"""Single source of truth for the package version.

Imported by ``__init__`` (public API), ``providers`` (HTTP User-Agent) and the
CLI so the version can never drift between the places that report it.
"""

__version__ = "0.4.0"
