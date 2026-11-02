"""mr-comic-smith: a local-first comic studio. Every story deserves panels."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mr-comic-smith")
except PackageNotFoundError:  # pragma: no cover - only when running from an uninstalled tree
    __version__ = "0.0.0"

__all__ = ["__version__"]
