# mcp/research_agent/research.py
from __future__ import annotations

import pathlib
import logging
from typing import Any, Dict, List, Optional, Tuple

try:
    from mcp.server.fastmcp import Context  # type: ignore
except Exception:
    Context = None  # type: ignore


log = logging.getLogger("research-agent")


def _read_text_file(p: pathlib.Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return p.read_text(errors="ignore")


def _extract_text_from_artifact(path: pathlib.Path) -> str:
    suffix = path.suffix.lower()
    try:
        if suffix in {".txt", ".md"}:
            return _read_text_file(path)
        if suffix == ".csv":
            import pandas as pd
            df = pd.read_csv(path)
            head = df.head(20).to_markdown(index=False)
            cols = ", ".join(map(str, df.columns.tolist()))
            return f"# CSV Preview\nColumns: {cols}\n\n{head}\n"
        if suffix == ".json":
            import json
            data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
            preview = str(data)[:8000]
            return f"# JSON Preview\n{preview}"
        if suffix == ".pdf":
            try:
                from pypdf import PdfReader
                reader = PdfReader(str(path))
                pages = []
                for pg in reader.pages[:10]:
                    pages.append(pg.extract_text() or "")
                return "\n\n".join(pages)
            except Exception:
                return f"[pdf:{path.name}] (text extraction failed; consider OCR)"
        if suffix == ".parquet":
            import pandas as pd
            df = pd.read_parquet(path)
            head = df.head(20).to_markdown(index=False)
            cols = ", ".join(map(str, df.columns.tolist()))
            return f"# Parquet Preview\nColumns: {cols}\n\n{head}\n"
        return _read_text_file(path)
    except Exception as e:
        return f"[artifact:{path.name}] extraction error: {e}"


def _safe_call_attr(obj: Any, names: List[str], *args, **kwargs):
    for n in names:
        fn = getattr(obj, n, None)
        if callable(fn):
            return fn(*args, **kwargs)
    raise AttributeError(f"None of {names} found on {type(obj).__name__}")

class Research:
    """
    Research pipeline that:
      1) Reads/understands artifacts
      2) Derives sub-topics from (goal + artifacts)
      3) Searches per sub-topic (search_llm)
      4) Reviews/aggregates findings (analyze_llm)
      5) Renders a research_report.md (returned as text)
    """

    def __init__(self, search_llm: Any, analyze_llm: Any, ctx: Optional[Context] = None):
        self.search_llm = search_llm
        self.analyze_llm = analyze_llm
        self.ctx = ctx

    def __init__(self, search_llm: Any, analyze_llm: Any, ctx: Optional[Context] = None):
        self.search_llm = search_llm
        self.analyze_llm = analyze_llm
        self.ctx = ctx

    async def _log(self, level: str, msg: str):
        if self.ctx is not None:
            getattr(self.ctx, level, self.ctx.info)(msg)  # type: ignore
        else:
            getattr(log, level, log.info)(msg)

    async def analyze_artifacts(
        self, user_goal: str, artifacts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        texts: List[Tuple[str, str]] = []
        for a in artifacts:
            p = pathlib.Path(a["path"])
            text = _extract_text_from_artifact(p)
            texts.append((a["name"], text[:20000]))

        dossier = "\n".join([f"### {n}\n{t}\n" for n, t in texts]) or "(no artifacts)"

        prompt = f"""
You are an expert research planner.

User goal:
{user_goal}

Artifact dossier (short previews):
{dossier}

1) Summarize each artifact in 2–4 bullet points focusing on what it contributes to the goal.
2) Produce 6–10 concise subtopics (prioritized) to comprehensively address the goal.
3) Suggest obvious gaps the artifacts do not cover.

Return JSON: {{
  "artifact_summaries": [{{"name": str, "bullets": [str, ...] }}],
  "proposed_subtopics": [str, ...],
  "gaps": [str, ...]
}}
"""
        analysis = self._call_analyze_llm_json(prompt, default={"artifact_summaries": [], "proposed_subtopics": [], "gaps": []})
        await self._log("info", f"[Research] artifact analysis -> {len(analysis.get('proposed_subtopics', []))} subtopics")
        return analysis

    async def search_subtopic(self, subtopic: str, goal: str, k: int = 6) -> List[Dict[str, str]]:
        q = f"{subtopic} — in service of: {goal}. Provide authoritative sources and recent developments."
        try:
            res = _safe_call_attr(self.search_llm, ["search", "ask", "query"], q, top_k=k)
        except TypeError:
            res = _safe_call_attr(self.search_llm, ["search", "ask", "query"], q, k)
        except Exception as e:
            await self._log("error", f"[Research] search error: {e}")
            return []

        items: List[Dict[str, str]] = []
        if isinstance(res, dict) and "results" in res:
            res = res["results"]
        if isinstance(res, list):
            for r in res[:k]:
                title = r.get("title") if isinstance(r, dict) else str(r)
                url = r.get("url") if isinstance(r, dict) else ""
                snippet = r.get("snippet") if isinstance(r, dict) else ""
                items.append({"title": str(title or ""), "url": str(url or ""), "snippet": str(snippet or "")})
        return items

    async def review_findings(
        self, goal: str, subtopic: str, findings: List[Dict[str, str]], artifact_context: str
    ) -> Dict[str, Any]:
        sources_txt = "\n".join([f"- {it.get('title','(untitled)')} :: {it.get('url','')}" for it in findings]) or "(no sources)"
        snippets = "\n\n".join([f"### {it.get('title','')}\n{it.get('snippet','')}" for it in findings]) or "(no snippets)"
        prompt = f"""
You are synthesizing research for a single subtopic.

Main goal:
{goal}

Subtopic:
{subtopic}

Artifact context (short):
{artifact_context}

External findings (links then snippets):
Links:
{sources_txt}

Snippets:
{snippets}

Tasks:
1) Write a concise synthesis (6–10 sentences) connecting findings back to the goal.
2) List 3–6 key takeaways.
3) Identify remaining open questions or next steps for this subtopic.

Return JSON: {{"synthesis": str, "takeaways": [str, ...], "open_questions": [str, ...]}}
"""
        return self._call_analyze_llm_json(prompt, default={"synthesis": "", "takeaways": [], "open_questions": []})

    async def run(self, user_goal: str, artifacts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Returns (no filesystem/S3 side-effects):
          {
            "report_md": "...",
            "subtopics": [...],
            "gaps": [...],
            "sources": [{"title","url","snippet"}, ...],
            "artifact_summaries": [...]
          }
        """
        analysis = await self.analyze_artifacts(user_goal, artifacts)
        subtopics: List[str] = analysis.get("proposed_subtopics", [])[:10]
        artifact_ctx = self._compact_artifact_summary(analysis.get("artifact_summaries", []))

        per_subtopic_notes: List[Dict[str, Any]] = []
        all_sources: List[Dict[str, str]] = []

        for idx, st in enumerate(subtopics, 1):
            await self._log("info", f"[Research] [{idx}/{len(subtopics)}] Searching: {st}")
            found = await self.search_subtopic(st, user_goal, k=6)
            all_sources.extend(found)
            review = await self.review_findings(user_goal, st, found, artifact_ctx)
            per_subtopic_notes.append({"subtopic": st, "notes": review, "sources": found})

        report_md = self._render_report_md(
            goal=user_goal,
            artifacts=artifacts,
            analysis=analysis,
            per_subtopic_notes=per_subtopic_notes,
        )

        return {
            "report_md": report_md,
            "subtopics": subtopics,
            "gaps": analysis.get("gaps", []),
            "sources": all_sources[:50],
            "artifact_summaries": analysis.get("artifact_summaries", []),
        }

    # ---------- internals ----------
    def _compact_artifact_summary(self, artifact_summaries: List[Dict[str, Any]]) -> str:
        parts = []
        for a in artifact_summaries[:10]:
            name = a.get("name") or a.get("artifact") or "(artifact)"
            bullets = a.get("bullets") or a.get("summary") or a
            if isinstance(bullets, list):
                bullets_txt = "; ".join(map(str, bullets))
            else:
                bullets_txt = str(bullets)
            parts.append(f"{name}: {bullets_txt}")
        return "\n".join(parts) if parts else "(no artifact summary)"

    def _render_report_md(
        self,
        goal: str,
        artifacts: List[Dict[str, Any]],
        analysis: Dict[str, Any],
        per_subtopic_notes: List[Dict[str, Any]],
    ) -> str:
        art_list = "\n".join([f"- {a['name']} ({a.get('size','?')} bytes)" for a in artifacts]) or "(none)"
        gaps = analysis.get("gaps", [])
        gaps_md = "\n".join([f"- {g}" for g in gaps]) if gaps else "(none)"

        sections = [
            f"# Research Report\n\n## Goal\n{goal}\n",
            "## Artifacts\n" + art_list + "\n",
            "## Initial Analysis\n",
            "### Proposed Subtopics\n" + "\n".join([f"- {s}" for s in analysis.get("proposed_subtopics", [])]) + "\n",
            "### Gaps Noted\n" + gaps_md + "\n",
            "## Findings by Subtopic\n",
        ]

        for blk in per_subtopic_notes:
            st = blk["subtopic"]
            notes = blk["notes"]
            sources = blk.get("sources", [])
            src_md = "\n".join([f"- [{s.get('title','(untitled)')}]({s.get('url','')})" for s in sources]) or "(no links)"
            sections.append(
                f"### {st}\n\n**Synthesis**\n\n{notes.get('synthesis','')}\n\n"
                f"**Key Takeaways**\n" + "\n".join([f"- {t}" for t in notes.get("takeaways", [])]) + "\n\n"
                f"**Open Questions**\n" + "\n".join([f"- {q}" for q in notes.get("open_questions", [])]) + "\n\n"
                f"**Sources**\n{src_md}\n"
            )

        sections.append("\n---\n_Generated by ResearchSubAgent_\n")
        return "\n".join(sections)

    def _call_analyze_llm_json(self, prompt: str, default: dict) -> dict:
        try:
            res = _safe_call_attr(self.analyze_llm, ["chat_json", "json", "ask_json", "chat"], prompt)
            if isinstance(res, dict):
                return res
            text = res if isinstance(res, str) else getattr(res, "content", None) or str(res)
            import json, re
            m = re.search(r"\{.*\}", text, flags=re.S)
            return json.loads(m.group(0)) if m else default
        except Exception as e:
            log.warning(f"analyze_llm JSON parse fallback: {e}")
            return default
