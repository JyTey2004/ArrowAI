# mcp/research_agent/components/analyzer.py
"""
Analyzer component for the Research pipeline.
- Reads/understands artifacts
- Derives sub-topics from (goal + artifacts)
- Returns a SearchPlan (list of SubTopics with rationale + questions)
"""

import re
import pathlib
import json

from typing import Any, List, Optional
from aws.s3_client import S3Client
from components.models import File, SearchPlan
from pydantic import ValidationError
from utils.LLMAdapter import LLMAdapter

import logging
logger = logging.getLogger("research-agent.analyzer")

JSON_BLOCK = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL|re.IGNORECASE)
ANY_BLOCK  = re.compile(r"```\s*\n(.*?)\n```", re.DOTALL)

class Analyzer:
  """
  Research pipeline that:
    1) Reads/understands artifacts
    2) Derives sub-topics from (goal + artifacts)
    3) Searches per sub-topic (search_llm)
    4) Reviews/aggregates findings (analyze_llm)
    5) Renders a research_report.md (returned as text)
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

  def sub_topics_path(self, thread_id: str) -> pathlib.Path:
      return self._research_dir(thread_id) / "SUB_TOPICS.md"

  def add_sub_topic(self, thread_id: str, content: str) -> None:
      p = self.sub_topics_path(thread_id)
      p.parent.mkdir(parents=True, exist_ok=True)
      prev = p.read_text(encoding="utf-8", errors="ignore") if p.exists() else "# Sub Topics\n\n"
      p.write_text(prev + content + "\n", encoding="utf-8")

  def _append_research_log(self, thread_id: str, text: str) -> None:
      logf = self.research_log_path(thread_id)
      logf.parent.mkdir(parents=True, exist_ok=True)
      header = "# Research Log\n\n"
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
          return {"sub_topics": []}
        
  @staticmethod
  def validate_plan(plan_dict: dict) -> SearchPlan:
    try:
        return SearchPlan(**plan_dict)
    except ValidationError as e:
        logger.warning(f"Search plan validation failed: {e}")
        # degrade gracefully
        return SearchPlan(sub_topics=[])

  async def analyze(self, thread_id:str, user_goal: str, artifacts: List[File], artifact_llm: LLMAdapter, analyze_llm: LLMAdapter) -> SearchPlan:
      """
      Research the analysis pipeline.
      - user_goal: user goal / topic
      - artifacts: list of {"name": ..., "path": ..., "size": ...} (local files)
      - returns: {"report_md": "...", "other_findings": ...}
      """
      # 1) Read/understand artifacts
      # 2) Returns a subtopic list + preliminary findings
      try:
        if artifacts:
          self._append_research_log(
            thread_id,
            f"## Artifacts meta"
          )

          # Read and understand the Artifacts
          for a in artifacts:  
            file_type = self.guess_file_type(a.name)
            
            if file_type in {"unknown"}:
              self._append_research_log(
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

              self._append_research_log(
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
                self._append_research_log(
                  thread_id,
                  f"### **{a.name}:** \n{result}\n\n"
                )
        else:
          self._append_research_log(
            thread_id,
            "## No artifacts provided\n\n"
          )
          
        # 2) Derive sub-topics from (goal + artifacts)
        research_log = self.research_log_path(thread_id).read_text(encoding="utf-8", errors="ignore")

        sub_topics_raw = analyze_llm.generate(f"RESEARCH_LOG: {research_log}\n\n")
        
        logger.info(f"Raw sub-topics output: {sub_topics_raw}")
        
        plan = self.try_parse_json(sub_topics_raw)
        # Sub-Topics in markdown
        for sub_topic in plan.get("sub_topics", []):
          if isinstance(sub_topic, dict):
            title = sub_topic.get("title", "No title")
            rationale = sub_topic.get("rationale", "No rationale")
            questions = sub_topic.get("questions", [])
            action = sub_topic.get("action", "Search/Analysis")
            questions_md = "\n".join([f"  - {q}" for q in questions])
            self.add_sub_topic(
              thread_id,
              f"### {title}\n**Action:** {action}\n**Rationale:** {rationale}\n**Questions:**\n{questions_md}\n"
            )
        
        plan = self.validate_plan(plan)
        return plan
      except Exception as e:
        logger.info(f"Error from Analyzer: {e}")
        
          
        

      

        

        
        