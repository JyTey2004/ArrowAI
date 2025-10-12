"""
Presentation Agent package.

Exports the high-level workflow builder alongside the current version string.
"""

from .workflow import build_presentation_graph

__all__ = ["__version__", "build_presentation_graph"]

__version__ = "0.1.0"

