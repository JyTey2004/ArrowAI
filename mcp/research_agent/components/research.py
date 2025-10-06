# mcp/research_agent/components/research.py
import asyncio
import datetime as dt
import pathlib
from typing import Any, List, Optional, Dict, Iterable, Tuple

from aws.s3_client import S3Client
from components.models import SearchPlan, AnalysisResult  # ensure SubTopic has action/country
from utils.LLMAdapter import LLMAdapter
from services.perplexity_client import PerplexityClient

# ---- helpers ----
def _now_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def _md_escape(s: str) -> str:
    # minimal markdown escaping for brackets/parentheses
    return s.replace("[", "\\[").replace("]", "\\]").replace("(", "\\(").replace(")", "\\)")

class Research:
    """
    Research pipeline that:
      1) Conducts searches and/or analyses per sub-topic
      2) Reviews/aggregates findings based on actions
      3) Returns a research_report.md (as text)
    """

    def __init__(
        self,
        base_tmp_dir: str = "tmp",
        s3_client: Optional[S3Client] = None,
        s3_prefix: str = "threads",   # s3://bucket/threads/<thread_id>/artifacts/...
        outputs_dirname: str = "outputs",
        inputs_dirname: str = "inputs",
        max_log_kb: int = 1024,       # soft cap per log
    ):
        self.s3_client = s3_client
        self.base_tmp = pathlib.Path(base_tmp_dir).resolve()
        self.s3_prefix = s3_prefix
        self.outputs_dirname = outputs_dirname
        self.inputs_dirname = inputs_dirname
        self.max_log_bytes = max_log_kb * 4096

    # ---- paths ----
    def _research_dir(self, thread_id: str) -> pathlib.Path:
        return self.base_tmp / thread_id / "research"

    def research_log_path(self, thread_id: str) -> pathlib.Path:
        return self._research_dir(thread_id) / "RESEARCH_LOG.md"

    def search_log_path(self, thread_id: str) -> pathlib.Path:
        return self._research_dir(thread_id) / "SEARCH_LOG.md"

    def analysis_log_path(self, thread_id: str) -> pathlib.Path:
        return self._research_dir(thread_id) / "ANALYSIS_LOG.md"

    # ---- log utils ----
    def _ensure_file(self, path: pathlib.Path, header: str):
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(header + "\n", encoding="utf-8")

    def _append_log(self, path: pathlib.Path, text: str, header: str):
        self._ensure_file(path, header)
        prev = path.read_bytes()
        # trim if oversized
        if len(prev) > self.max_log_bytes:
            # keep last 90%
            keep = prev[int(len(prev) * 0.1):]
            path.write_bytes(keep)
        with path.open("a", encoding="utf-8") as f:
            f.write(text.rstrip() + "\n")

    def _append_search_log(self, thread_id: str, text: str):
        ts = _now_iso()
        self._append_log(
            self.search_log_path(thread_id),
            f"\n---\n\n**{ts}**\n\n{text}\n",
            "# Search Log"
        )

    def _append_analysis_log(self, thread_id: str, text: str):
        ts = _now_iso()
        self._append_log(
            self.analysis_log_path(thread_id),
            f"\n---\n\n**{ts}**\n\n{text}\n",
            "# Analysis Log"
        )

    def _read_text_or_blank(self, path: pathlib.Path) -> str:
        return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""

    # ---- main ----
    async def research(
        self,
        thread_id: str,
        task: str,
        search_plan: SearchPlan,
        search_llm: PerplexityClient,
        analyze_llm: LLMAdapter,
        summary_llm: LLMAdapter,
        upload_to_s3: bool = False,
    ) -> AnalysisResult:
        """
        Conduct searches and/or analyses per sub-topic, then review/aggregate findings.
        Returns the research_report.md string (and optionally uploads logs/report to S3).
        """
        # ensure base logs exist
        self._ensure_file(self.research_log_path(thread_id), "# Research Log")
        self._ensure_file(self.search_log_path(thread_id), "# Search Log")
        self._ensure_file(self.analysis_log_path(thread_id), "# Analysis Log")

        report_lines = [
            "# Research Report",
            "## Task",
            task.strip(),
            "## Findings",
        ]

        for idx, sub_topic in enumerate(search_plan.sub_topics, 1):
            title = getattr(sub_topic, "title", f"Sub-topic {idx}")
            rationale = getattr(sub_topic, "rationale", "").strip()
            action = (getattr(sub_topic, "action", "search") or "search").lower()
            country = getattr(sub_topic, "country", None)
            questions = list(getattr(sub_topic, "questions", []) or [])

            report_lines.append(f"### {idx}. {_md_escape(title)}")
            if rationale:
                report_lines.append(f"**Rationale:** {_md_escape(rationale)}")

            findings: List[str] = []

            if action == "search":
                results = search_llm.search(
                    query=questions if questions else title,
                    country=country,
                    max_results=5
                )
                if questions:
                    findings.append(f"**Search Queries:** " + ", ".join(_md_escape(q) for q in questions))

                # pretty-print search results
                for r in results: # result object from Perplexity
                    t = getattr(r, "title", "No Title")
                    u = getattr(r, "url", None)
                    s = getattr(r, "snippet", "").strip().replace("\n", " ")
                    d = getattr(r, "date") or "N/A"
                    lu = getattr(r, "last_updated") or "N/A"
                    if u:
                        findings.append(f"- [{t}]({u})\n  - {s}\n  - Date: {d}\n  - Last Updated: {lu}")
                    else:
                        findings.append(f"- {t}\n  - {s}")

                # append to SEARCH_LOG
                self._append_search_log(
                    thread_id,
                    f"### {title}\n" + "\n".join(findings)
                )

            elif action == "analysis":
                research_log = self._read_text_or_blank(self.research_log_path(thread_id))
                search_log = self._read_text_or_blank(self.search_log_path(thread_id))
                q_block = "".join(f"- {q}\n" for q in questions)
                prompt = (
                    f"RESEARCH_LOG.md:\n{research_log}\n\n"
                    f"SEARCH_LOG.md:\n{search_log}\n\n"
                    f"Questions:\n{q_block}\n"
                    f"Instruction: Provide a concise, sourced synthesis answering the questions. "
                    f"Use bullet points and short paragraphs."
                )
                analysis_result = analyze_llm.generate(prompt)
                findings.append(analysis_result.strip())
                self._append_analysis_log(thread_id, f"### {title}\n{analysis_result.strip()}")

            else:
                findings.append(f"_Unsupported action '{action}'. Skipping._")

            if findings:
                report_lines.extend(findings)
            else:
                report_lines.append("**Findings:** No findings available.")

            report_lines.append("\n---\n")

        report = "\n".join(report_lines).strip() + "\n"
        
        artifacts = []

        # optional S3 uploads
        if upload_to_s3 and self.s3_client:
            base_key = f"{self.s3_prefix}/{thread_id}/artifacts/research"
            for name, path in [
                ("research_report.md", self._research_dir(thread_id) / "research_report.md"),
                ("RESEARCH_LOG.md", self.research_log_path(thread_id)),
                ("SEARCH_LOG.md", self.search_log_path(thread_id)),
                ("ANALYSIS_LOG.md", self.analysis_log_path(thread_id)),
            ]:
                if name == "research_report.md":
                    path.write_text(report, encoding="utf-8")

                if path.exists():
                    key = f"{base_key}/{name}"
                    # assuming your S3Client has put_file like (local_path, key)
                    try:
                        self.s3_client.put_file(str(path), key)
                        artifacts.append({
                            "name": name,
                            "path": f"s3://{self.s3_client.bucket}/{key}",
                            "description": f"",
                            "size": path.stat().st_size,
                        })
                    except Exception:
                        # non-fatal
                        pass
                      
                    
        summary_prompt = (
            f"Task:\n{task}\n\n"
            f"Research Report:\n{report}\n\n"
            f"Artifacts:\n" + "\n".join(f"- {a['name']} ({a['path']}) size: {a['size']} bytes" for a in artifacts) + "\n\n"
            f"JSON Schema:\n{AnalysisResult.model_json_schema()}\n\n"
        )
        summary_raw = summary_llm.generate(summary_prompt)

        summary_obj = AnalysisResult.model_validate_json(summary_raw)
        summary = f"### Key Findings\n{summary_obj.key_findings}\n\n### Gaps\n{summary_obj.gaps}\n"
        if summary_obj.artifacts:
            artifacts_md = "\n".join(
                f"- {a.name} ({a.path})" + (f": {a.description}" if a.description else "")
                for a in summary_obj.artifacts
            )
            summary += f"\n### Artifacts\n{artifacts_md}\n"
        
        report += "\n## Summary\n" + summary.strip() + "\n"
        
        self._append_log(
            self.research_log_path(thread_id),
            f"\n## Summary\n\n{summary.strip()}\n",
            "# Research Log"
        )

        return summary_obj
