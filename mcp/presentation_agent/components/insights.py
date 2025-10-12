"""
Statistical insight generator that leans on the shared code sandbox.

The goal is to surface slide-ready metrics and charts by blending structured
datasets with free-form research context.
"""

from __future__ import annotations

import shutil
import textwrap
from pathlib import Path
from typing import Iterable, List

from components.executor import CodeSandbox, ExecRequest, ExecResult
from utils.LLMAdapter import LLMAdapter

from aws.s3_client import S3Client

from components.models import DataAsset, InsightGenerationRequest, InsightGenerationResponse


class InsightGenerator:
    """Coordinate sandbox runs that produce statistical insights and visuals."""

    def __init__(
        self,
        sandbox: CodeSandbox,
        s3_client: S3Client | None,
        code_llm: LLMAdapter,
    ) -> None:
        self.sandbox = sandbox
        self.s3_client = s3_client
        self.code_llm = code_llm

    # ------------------------
    # Public API
    # ------------------------
    def generate(self, request: InsightGenerationRequest) -> InsightGenerationResponse:
        """Run a single sandbox cell tuned for slide-friendly analytics."""
        thread_id = request.thread_id
        self.sandbox.get_kernel(thread_id)  # ensures layout

        local_assets = self._materialize_assets(thread_id, request.data_assets)

        cel_header = self._format_cel_entry(request, local_assets)
        self.sandbox._append_cel_log(thread_id, cel_header)  # type: ignore[attr-defined]
        self.sandbox._append_run_log(thread_id, "\n\n## Presentation Insight\n")  # type: ignore[attr-defined]
        self.sandbox._append_artifact_log(thread_id, self._artifact_note(local_assets))  # type: ignore[attr-defined]

        exec_req = ExecRequest(
            code=None,
            language="python",
            task=self._format_task(request, local_assets),
            timeout_s=request.timeout_s,
            pip=request.pip_packages or None,
            use_llm_writer=True,
            repair_attempts=request.repair_attempts or 0,
        )

        execution_context = self._execution_context(request, local_assets)
        result = self.sandbox.exec_cell(
            thread_id=thread_id,
            req=exec_req,
            code_llm=self.code_llm,
            eval_llm=None,
            execution_context=execution_context,
        )

        return self._build_response(result)

    # ------------------------
    # Helpers
    # ------------------------
    def _materialize_assets(self, thread_id: str, assets: Iterable[DataAsset]) -> List[dict]:
        """Download or copy assets into the sandbox inputs directory."""
        if not assets:
            return []

        inputs_dir = self._inputs_dir(thread_id)
        inputs_dir.mkdir(parents=True, exist_ok=True)

        prepared: List[dict] = []
        for asset in assets:
            dest_path = inputs_dir / asset.name
            try:
                if asset.path.startswith("s3://"):
                    if not self.s3_client:
                        raise RuntimeError("S3 client not configured for presentation agent.")
                    self.s3_client.download_file(asset.path, str(dest_path), version_id=asset.version_id)
                else:
                    src = Path(asset.path)
                    if not src.exists():
                        raise FileNotFoundError(f"Asset '{asset.name}' not found at {asset.path}")
                    if src.is_file():
                        shutil.copy2(src, dest_path)
                    else:
                        if dest_path.exists():
                            shutil.rmtree(dest_path)
                        shutil.copytree(src, dest_path)

                size = dest_path.stat().st_size if dest_path.exists() and dest_path.is_file() else asset.size
                prepared.append(
                    {
                        "name": asset.name,
                        "source_path": asset.path,
                        "local_path": str(dest_path),
                        "size": size,
                        "description": asset.description or "",
                    }
                )
            except Exception as exc:
                raise RuntimeError(f"Failed to stage asset '{asset.name}': {exc}") from exc
        return prepared

    def _inputs_dir(self, thread_id: str) -> Path:
        run_dir = self.sandbox.base_tmp / thread_id
        return run_dir / self.sandbox.inputs_dirname

    @staticmethod
    def _format_cel_entry(request: InsightGenerationRequest, assets: List[dict]) -> str:
        bullet_lines = "\n".join(
            f"- {a['name']}: {a['source_path']} ({(a.get('size') or 'unknown')} bytes)"
            for a in assets
        ) or "- No data assets supplied."

        research = request.research_context.strip() if request.research_context else "n/a"

        return textwrap.dedent(
            f"""
            ## Insight Task
            **Goal:** {request.task}

            **Research context:** {research}

            **Data assets staged:**
            {bullet_lines}
            """
        ).strip()

    @staticmethod
    def _artifact_note(assets: List[dict]) -> str:
        if not assets:
            return "## Data Assets\nNo structured datasets provided.\n"

        lines = "\n".join(
            f"- {a['name']} → {a['local_path']} (source: {a['source_path']})"
            for a in assets
        )
        return f"## Data Assets\n{lines}\n"

    @staticmethod
    def _format_task(request: InsightGenerationRequest, assets: List[dict]) -> str:
        asset_blurbs = "\n".join(
            f"- {a['name']}: stored at {a['local_path']} (source {a['source_path']}). {a.get('description', '')}"
            for a in assets
        ) or "- No tabular data was provided."

        research = request.research_context.strip() if request.research_context else "No additional research context supplied."

        return textwrap.dedent(
            f"""
            Prepare slide-ready statistics and visuals.
            User goal: {request.task}

            Research context (use to annotate insights, cite qualitative findings, or craft captions):
            {research}

            Available data assets (all already downloaded under INPUTS_DIR):
            {asset_blurbs}

            Focus on:
            1. Computing statistically sound metrics (averages, changes, confidence intervals, correlations) that support storytelling.
            2. Building clear charts for slide decks (bar, line, combo, small multiples). Save each figure under outputs/ with descriptive names.
            3. Summarising insights in prose that can be copy-pasted into slides, explicitly tying quantitative findings to the research context.
            4. Printing key metrics with `EVIDENCE:` lines and registering generated artifacts with `ARTIFACT:` lines.
            5. Ending with `DONE`.
            """
        ).strip()

    @staticmethod
    def _execution_context(request: InsightGenerationRequest, assets: List[dict]) -> str:
        context_sections = [
            f"Primary task: {request.task}",
            f"Research highlights: {request.research_context or 'n/a'}",
            "Data inventory:",
        ]
        if assets:
            context_sections.extend(
                f"- {a['name']}: {a['local_path']} (source {a['source_path']})" for a in assets
            )
        else:
            context_sections.append("- No structured data provided; rely on research context.")
        return "\n".join(context_sections)

    @staticmethod
    def _build_response(result: ExecResult) -> InsightGenerationResponse:
        artifacts_payload = [a.model_dump() if hasattr(a, "model_dump") else dict(a) for a in result.files_out or []]
        code_path = ""
        if isinstance(result.code, dict):
            code_path = result.code.get("path") or ""

        return InsightGenerationResponse(
            ok=result.ok,
            summary=result.summary or (result.stdout[:500] if result.stdout else ""),
            stdout=result.stdout or "",
            stderr=result.stderr or "",
            artifacts=artifacts_payload,
            code_reference=code_path or None,
        )
