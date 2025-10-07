# mcp/research_agent/components/analyzer.py
"""
Analyzer component for the Research pipeline.
- Reads/understands artifacts
- Produces a focused set of research questions aligned to the user goal.
"""

import re
import pathlib
import json

from typing import Any, List, Optional
from aws.s3_client import S3Client
from components.models import File, QuestionPlan
from pydantic import ValidationError
from utils.LLMAdapter import LLMAdapter

import logging
logger = logging.getLogger("research-agent.analyzer")

JSON_BLOCK = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL|re.IGNORECASE)
ANY_BLOCK  = re.compile(r"```\s*\n(.*?)\n```", re.DOTALL)

class Analyzer:
  """
  Research planning component that:
    1) Reads/understands artifacts
    2) Appends findings to the research log
    3) Derives an initial list of research questions (max three)
  """

  def __init__(
      self, 
      base_tmp_dir: str = "tmp",
      s3_client: Optional[S3Client] = None,
      s3_prefix: str = "threads",  # s3://bucket/threads/<thread_id>/artifacts/...
      outputs_dirname: str = "outputs",
      inputs_dirname: str = "inputs",
  ):
      self.s3_client = s3_client
      self.base_tmp = pathlib.Path(base_tmp_dir).resolve()
      self.s3_prefix = s3_prefix
      self.outputs_dirname = outputs_dirname
      self.inputs_dirname = inputs_dirname
    
  def _research_dir(self, thread_id: str) -> pathlib.Path:
      return self.base_tmp / thread_id / "research"
    
  def research_log_path(self, thread_id: str) -> pathlib.Path:
      return self._research_dir(thread_id) / "RESEARCH_LOG.md"
    
  def _artifacts_log_path(self, thread_id: str) -> pathlib.Path:
      return self._research_dir(thread_id) / "ARTIFACTS_LOG.md"

  def _append_research_log(self, thread_id: str, text: str) -> None:
      logf = self.research_log_path(thread_id)
      logf.parent.mkdir(parents=True, exist_ok=True)
      header = "# Research Log\n\n"
      prev = logf.read_text(encoding="utf-8", errors="ignore") if logf.exists() else header
      logf.write_text(prev + text + "\n", encoding="utf-8")
      
  def _append_artifacts_log(self, thread_id: str, text: str) -> None:
      logf = self._artifacts_log_path(thread_id)
      logf.parent.mkdir(parents=True, exist_ok=True)
      header = "# Artifacts Log\n\n"
      prev = logf.read_text(encoding="utf-8", errors="ignore") if logf.exists() else header
      logf.write_text(prev + text + "\n", encoding="utf-8")

  def analyze_prompt(self, user_goal: str, filename: str, description: str, s3_presign_url: str, s3_file_type: str):
    base_prompt = {
        "role": "user",
          "content": [
            {"type": "input_text", "text": (
              f"Goal: {user_goal}\n\n"
              f"Output all relevant information from {filename}, in a markdown bullet list without quotes."
            )},
        ]
    }
    
    if description:
      base_prompt["content"].insert(1, {"type": "input_text", "text": f"File description: {description}\n\n"})
    
    if s3_file_type in {"pdf", "docx", "pptx"}:
      base_prompt["content"].append({
        "type": "input_file",
        "file_url": s3_presign_url,
      })
      return [base_prompt]
    elif s3_file_type in {"png", "jpg", "jpeg", "gif", "bmp"}:
      base_prompt["content"].append({
        "type": "input_image",
        "image_url": s3_presign_url,
      })
      return [base_prompt]
    else:
      logger.warning(f"Unsupported artifact file type: {s3_file_type}")
      return []
    
  def text_analyze_prompt(self, user_goal: str, filename: str, content: str):
    return [
      {
        "role": "user",
        "content": [
          {"type": "input_text", "text": (
            f"Goal: {user_goal}\n\n"
            f"File: {filename}\n\n"
            f"Output all relevant information from the file, in a markdown bullet list without quotes.\n\n"
            f"BEGIN FILE CONTENT\n{content}\nEND FILE CONTENT"
          )}
        ]
      }
    ]
    
  def guess_file_type(self, filename: str) -> str:
    ext = filename.lower().split(".")[-1]
    ext = "." + ext
    if ext in {".pdf"}:
      return "pdf"
    elif ext in {".docx", ".doc"}:
      return "docx"
    elif ext in {".pptx", ".ppt"}:
      return "pptx"
    elif ext in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}:
      return "png"
    else:
      return "unknown"
      
  def _extract_markdown(self, output: str):
    if "```" not in output:
        return output.strip()
    # Prefer a language fence block if present
    m = re.search(r"```(?:markdown|md)?\s*\n(.*?)\n```", output, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # Fallback: remove any backticks naively
    return output.replace("```markdown", "").replace("```", "").strip()

  def try_parse_json(self, s: str) -> dict:
      # Prefer json fence if present
      m = JSON_BLOCK.search(s) or ANY_BLOCK.search(s)
      if m:
          s = m.group(1).strip()
      s = s.strip()

      # Happy path
      try:
          return json.loads(s)
      except json.JSONDecodeError:
          pass

      # Lightweight repairs: strip trailing commas, replace smart quotes
      repaired = (
          s.replace("“","\"").replace("”","\"").replace("’","'")
      )
      repaired = re.sub(r",(\s*[\]}])", r"\1", repaired)  # trailing commas
      try:
          return json.loads(repaired)
      except Exception:
          # last ditch: return empty shape you expect
          return {"questions": [], "rationale": ""}

  def _fallback_questions(self, user_goal: str) -> List[str]:
      topic = (user_goal or "the topic").strip().rstrip("?")
      if not topic:
          topic = "the topic"
      return [
          f"What is the current landscape for {topic}?",
          f"What recent developments or data points matter most for {topic}?",
          f"What open questions remain about {topic}?",
      ]

  def _build_question_plan(self, data: dict, user_goal: str) -> QuestionPlan:
      raw_questions = data.get("questions") or []
      cleaned: List[str] = []
      for item in raw_questions:
          if isinstance(item, str):
              q = item.strip()
              if q and q not in cleaned:
                  cleaned.append(q)

      if not cleaned:
          cleaned = []

      fallback = self._fallback_questions(user_goal)
      while len(cleaned) < 3 and fallback:
          candidate = fallback[len(cleaned)]
          if candidate not in cleaned:
              cleaned.append(candidate)

      # Ensure max three questions
      cleaned = cleaned[:3] if cleaned else fallback[:3]

      rationale = data.get("rationale")
      if isinstance(rationale, str):
          rationale = rationale.strip() or None
      else:
          rationale = None

      return QuestionPlan(questions=cleaned, rationale=rationale)

  async def analyze(self, thread_id:str, user_goal: str, artifacts: List[File], artifact_llm: LLMAdapter, analyze_llm: LLMAdapter) -> QuestionPlan:
      """
      Research the analysis pipeline.
      - user_goal: user goal / topic
      - artifacts: list of {"name": ..., "path": ..., "size": ...} (local files)
      - returns: QuestionPlan with up to three prioritized questions
      """
      # 1) Read/understand artifacts
      # 2) Returns a subtopic list + preliminary findings
      try:
        if artifacts:
          
          artifact_log = self._artifacts_log_path(thread_id)
          artifact_log.parent.mkdir(parents=True, exist_ok=True)
          artifact_log_txt = artifact_log.read_text(encoding="utf-8", errors="ignore") # this will be empty if file doesn't exist
                    
          # Read and understand the Artifacts
          for a in artifacts:  
            if a.name in artifact_log_txt:
              logger.info(f"Skipping previously analyzed artifact: {a.name}")
              continue  # skip already analyzed artifacts
            
            file_type = self.guess_file_type(a.name)
            
            if file_type in {"unknown"}:
              self._append_artifacts_log(
                thread_id,
                f"- **{a.name}:** \n  - Skipped (unsupported file type)\n\n"
              )
              continue
            elif file_type in {"pdf", "docx", "pptx", "png", "jpg", "jpeg", "gif", "bmp"}:
              # Build a s3 presigned URL so we can pass this to the LLM
              s3_url = ""
              if self.s3_client and a.path.startswith("s3://"):
                s3_url = self.s3_client.presigned_get(key=a.path, expires_in=360) # expires in 6 mins
                logger.info(f"Artifact {a.name} presigned URL: {s3_url}")

              artifact_prompt = self.analyze_prompt(user_goal, a.name, a.description, s3_url, file_type)
              result = artifact_llm.response(artifact_prompt)
              result = self._extract_markdown(result)

              self._append_artifacts_log(
                thread_id,
                f"### **{a.name}:** \n{result}\n\n"
              )
            elif file_type in {"txt", "log", "md"}:
              if self.s3_client and a.path.startswith("s3://"):
                content, _ = self.s3_client.get_bytes(a.path)
                content_str = content.decode("utf-8", errors="ignore")
                content_str = content_str[:4000]  # limit to first 4k chars

                artifact_prompt = self.text_analyze_prompt(user_goal, a.name, content_str)
                result = artifact_llm.response(artifact_prompt)
                result = self._extract_markdown(result)
                self._append_artifacts_log(
                  thread_id,
                  f"### **{a.name}:** \n{result}\n\n"
                )
        else:
          pass
          
        # 2) Derive sub-topics from (goal + artifacts)
        research_log = self.research_log_path(thread_id).read_text(encoding="utf-8", errors="ignore")
        artifact_log = self._artifacts_log_path(thread_id).read_text(encoding="utf-8", errors="ignore")

        planner_raw = analyze_llm.generate(
          f"USER_GOAL: {user_goal}\n\n"
          f"ARTIFACTS_LOG:\n{artifact_log if artifact_log else 'No artifacts provided.'}\n\n"
          f"RESEARCH_LOG:\n{research_log}\n\n"
          "Return strictly formatted JSON as instructed."
          f"Json Schema: {QuestionPlan.model_json_schema()}"
        )

        logger.info(f"Generated initial questions: {planner_raw}")

        plan_dict = self.try_parse_json(planner_raw)
        question_plan = self._build_question_plan(plan_dict, user_goal)

        questions_md = "\n".join([f"- {q}" for q in question_plan.questions])
        self._append_research_log(
          thread_id,
          (
            "## Initial Research Questions\n"
            f"{question_plan.rationale or 'Derived from artifact review.'}\n\n"
            f"{questions_md}\n"
          )
        )

        return question_plan
      except Exception as e:
        logger.info(f"Error from Analyzer: {e}")
        fallback_plan = QuestionPlan(questions=self._fallback_questions(user_goal))
        self._append_research_log(
          thread_id,
          "## Initial Research Questions\nPlanner failed, using fallback prompts.\n"
          + "\n".join(f"- {q}" for q in fallback_plan.questions)
        )
        return fallback_plan
        