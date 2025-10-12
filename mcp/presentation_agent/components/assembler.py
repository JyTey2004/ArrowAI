"""
Deck assembly helpers for the presentation agent scaffold.
"""

from __future__ import annotations

import uuid

from .models import PresentationAssemblyRequest, PresentationAssemblyResponse


class DeckAssembler:
    """Combine drafted slides into a deliverable artifact."""

    def assemble(self, request: PresentationAssemblyRequest) -> PresentationAssemblyResponse:
        """
        Create a placeholder artifact reference.

        For now we park the assembled result under an in-memory URI so the rest
        of the agent pipeline has something to hand back to the user interface.
        When we wire this up to S3 or local storage we can replace this stub
        with actual persistence and formatting.
        """
        slide_count = len(request.slides)
        pseudo_uri = f"memory://presentation/{uuid.uuid4().hex}"

        return PresentationAssemblyResponse(
            artifact_path=pseudo_uri,
            preview_snippet=(
                f"Generated a {slide_count}-slide deck placeholder "
                f"in {request.format} format. Persist actual files later."
            ),
            slide_count=slide_count,
        )

