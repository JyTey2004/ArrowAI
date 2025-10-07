# mcp/research_agent/components/research.py
import datetime as dt
import pathlib
import json
from typing import Any, List, Optional, Dict
import logging

from aws.s3_client import S3Client
from components.models import QuestionPlan, AnalysisResult
from utils.LLMAdapter import LLMAdapter
from services.perplexity_client import PerplexityClient

logger = logging.getLogger(__name__)

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
    
    def artifacts_log_path(self, thread_id: str) -> pathlib.Path:
        return self._research_dir(thread_id) / "ARTIFACTS_LOG.md"

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

    def _normalise_result(self, item: Any) -> Dict[str, Any]:
        if isinstance(item, dict):
            return item
        data = {}
        for attr in ["title", "url", "source", "snippet", "date", "last_updated", "score", "author"]:
            data[attr] = getattr(item, attr, None)
        # Some SDKs expose link via `source_url` or `link`
        if not data.get("url"):
            data["url"] = getattr(item, "source_url", None) or getattr(item, "link", None)
        if not data.get("snippet"):
            data["snippet"] = getattr(item, "text", None)
        return data

    def _format_search_results(self, results: List[Any]) -> List[str]:
        lines: List[str] = []
        for idx, item in enumerate(results, 1):
            data = self._normalise_result(item)
            title = data.get("title") or f"Result {idx}"
            url = data.get("url")
            snippet = (data.get("snippet") or "").strip().replace("\n", " ")
            date = data.get("date") or data.get("published_at") or "N/A"
            score = data.get("score")
            if url:
                lines.append(f"- [{_md_escape(title)}]({url})")
            else:
                lines.append(f"- {_md_escape(title)}")
            details = []
            if snippet:
                details.append(snippet)
            if date and date != "N/A":
                details.append(f"Date: {date}")
            last_updated = data.get("last_updated") or data.get("updated_at")
            if last_updated:
                details.append(f"Updated: {last_updated}")
            if score is not None:
                details.append(f"Score: {score}")
            if details:
                lines.append("  - " + " | ".join(details))
        if not lines:
            lines.append("- No results returned or query failed.")
        return lines

    def _parse_analysis_json(self, payload: str) -> Dict[str, Any]:
        try:
            # Remove all ```json ... ``` wrappers if present
            if payload.strip().startswith("```") and payload.strip().endswith("```"):
                cleaned = payload.strip().strip("`").strip()
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].strip()
                data = json.loads(cleaned)
            else:
                data = json.loads(payload)
        except Exception:
            try:
                cleaned = payload.strip().strip("`")
                data = json.loads(cleaned)
            except Exception:
                data = {}

        summary = data.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            summary = "No summary generated."

        next_questions = []
        raw_questions = data.get("next_questions") or []
        if isinstance(raw_questions, list):
            for item in raw_questions:
                if isinstance(item, str):
                    q = item.strip()
                    if q and q not in next_questions:
                        next_questions.append(q)
        next_questions = next_questions[:3]

        task_answered = bool(data.get("task_answered"))

        return {
            "summary": summary.strip(),
            "next_questions": next_questions,
            "task_answered": task_answered,
        }

    # ---- main ----
    async def research(
        self,
        thread_id: str,
        task: str,
        initial_plan: QuestionPlan,
        search_llm: PerplexityClient,
        analyze_llm: LLMAdapter,
        summary_llm: LLMAdapter,
        upload_to_s3: bool = False,
        max_iterations: int = 5,
    ) -> AnalysisResult:
        """
        Iteratively search and analyse until the task can be answered or we hit max iterations.
        """
        # ensure base logs exist
        self._ensure_file(self.research_log_path(thread_id), "# Research Log")
        self._ensure_file(self.search_log_path(thread_id), "# Search Log")
        self._ensure_file(self.analysis_log_path(thread_id), "# Analysis Log")
        self._ensure_file(self.artifacts_log_path(thread_id), "# Artifacts Log")

        questions = list(initial_plan.questions)
        analysis_sections: List[str] = []
        resolved = False

        for iteration in range(1, max_iterations + 1):
            queries = [q.strip() for q in questions if isinstance(q, str) and q.strip()]
            if not queries:
                break

            results = search_llm.search(query=queries, max_results=8)
            if isinstance(results, dict):
                results_list = results.get("results") or results.get("sources") or []
            else:
                results_list = results if isinstance(results, list) else []
            formatted_results = self._format_search_results(results_list)

            search_entry_lines = [
                f"## Iteration {iteration}",
                "### Queries",
                *[f"- {q}" for q in queries],
                "",
                "### Results",
                *formatted_results,
            ]
            self._append_search_log(thread_id, "\n".join(search_entry_lines))

            search_log_txt = self._read_text_or_blank(self.search_log_path(thread_id))
            analysis_log_txt = self._read_text_or_blank(self.analysis_log_path(thread_id))
            artifacts_log_txt = self._read_text_or_blank(self.artifacts_log_path(thread_id))
            
            # Split the search results to only the last 3 iterations
            search_iterations = search_log_txt.split("## Iteration ")
            if len(search_iterations) > 4:
                search_log_txt = "## Iteration " + "## Iteration ".join(search_iterations[-4:])
                
            # Limit the analysis log to the last 3 iterations
            analysis_iterations = analysis_log_txt.split("### Iteration ")
            if len(analysis_iterations) > 4:
                analysis_log_txt = "### Iteration " + "### Iteration ".join(analysis_iterations[-4:])
   
            analysis_prompt = (
                f"USER_GOAL:\n{task}\n\n"
                f"AGGREGATED_SEARCH_LOG (last 4 iterations):\n{search_log_txt}\n\n"
                f"PRIOR_ANALYSIS (last 4 iterations):\n{analysis_log_txt}\n\n"
                f"ARTIFACTS_LOG:\n{artifacts_log_txt}\n\n"
                f"You are analysing iteration {iteration}.\n"
                "Return STRICT JSON with keys: summary (markdown string), next_questions (array of up to three strings), task_answered (boolean).\n"
                "Summary must reference insights from ALL iterations so far, clearly citing new findings this round.\n"
                "If the task appears answered, set task_answered true and emit an empty next_questions array, but still summarize any outstanding questions or areas for further exploration.\n"
            )
            
            logger.info(f"Iteration {iteration} analysis prompt: {analysis_prompt}")

            analysis_raw = analyze_llm.generate(analysis_prompt)
            logger.info(f"Iteration {iteration} analysis data: {analysis_raw}")
            analysis_data = self._parse_analysis_json(analysis_raw)
            summary_text = analysis_data["summary"]
            next_questions = analysis_data["next_questions"]
            resolved = analysis_data["task_answered"]
            
            self._append_analysis_log(thread_id, f"## Iteration {iteration} Summary\n{summary_text}")
            analysis_sections.append(f"### Iteration {iteration}\n{summary_text}")

            if resolved:
                questions = []
                break

            questions = next_questions

            if not questions:
                break

        report_sections = [
            "# Research Report",
            "## Task",
            task.strip(),
            "## Initial Questions",
            *[f"- {q}" for q in initial_plan.questions],
        ]

        if initial_plan.rationale:
            report_sections.extend(["", "### Planner Rationale", initial_plan.rationale.strip()])

        if analysis_sections:
            report_sections.extend(["", "## Iteration Summaries", "", *analysis_sections])
        else:
            report_sections.extend(["", "## Iteration Summaries", "No summaries generated."])

        report = "\n".join(report_sections).strip() + "\n"

        artifacts = []
                                          
        search_log_snapshot = self._read_text_or_blank(self.search_log_path(thread_id))
        analysis_log_snapshot = self._read_text_or_blank(self.analysis_log_path(thread_id))
        research_log_snapshot = self._read_text_or_blank(self.research_log_path(thread_id))
        
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
            f"Initial Questions:\n" + "\n".join(f"- {q}" for q in initial_plan.questions) + "\n\n"
            f"Research Log:\n{research_log_snapshot}\n\n"
            f"Search Log:\n{search_log_snapshot}\n\n"
            f"Analysis Log:\n{analysis_log_snapshot}\n\n"
            f"Research Report Draft:\n{report}\n\n"
            f"Artifacts:\n" + "\n".join(
                f"- {a['name']} ({a['path']}) size: {a['size']} bytes" for a in artifacts
            ) + "\n\n"
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
            f"\n## Summary\n\n{summary.strip()}\n---",
            "# Research Log"
        )
        
        # Update the research_report.md with final summary
        report_path = self._research_dir(thread_id) / "research_report.md"
        report_path.write_text(report, encoding="utf-8")
        if upload_to_s3 and self.s3_client:
            key = f"{self.s3_prefix}/{thread_id}/artifacts/research/research_report.md"
            try:
                self.s3_client.put_file(str(report_path), key)
            except Exception:
                pass  # non-fatal
        
        return summary_obj
