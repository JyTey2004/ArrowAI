"""
Component exports for the presentation agent.

Each component currently provides only skeletal behavior to illustrate the
intended flow of data through the agent. The concrete implementations will be
filled in once the orchestration logic is finalized.
"""

from components.outline import PresentationOutlinePlanner
from components.slide_writer import SlideDraftWriter
from components.assembler import DeckAssembler
from components.insights import InsightGenerator

__all__ = [
    "PresentationOutlinePlanner",
    "SlideDraftWriter",
    "DeckAssembler",
    "InsightGenerator",
]
