# mcp/code_agent/components/artifacts_analyzer.py
"""
Analyzer component for the artifacts pipeline.
- Reads/understands artifacts
"""

import re
import pathlib
import json

from typing import Any, List, Optional
from aws.s3_client import S3Client
from components.models import File
from pydantic import ValidationError
from utils.LLMAdapter import LLMAdapter
from components.executor import CodeSandbox, ExecRequest

import logging
logger = logging.getLogger("artifacts-agent.analyzer")

JSON_BLOCK = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL|re.IGNORECASE)
ANY_BLOCK  = re.compile(r"```\s*\n(.*?)\n```", re.DOTALL)

class ArtifactsAnalyzer:
    """
    artifacts pipeline that:
        1) Reads/understands artifacts

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
        
    def _artifacts_dir(self, thread_id: str) -> pathlib.Path:
        return self.base_tmp / thread_id 
        
    def artifacts_log_path(self, thread_id: str) -> pathlib.Path:
        return self._artifacts_dir(thread_id) / "ARTIFACTS.md"

    def sub_topics_path(self, thread_id: str) -> pathlib.Path:
        return self._artifacts_dir(thread_id) / "SUB_TOPICS.md"

    def _append_artifacts_log(self, thread_id: str, text: str) -> None:
        logf = self.artifacts_log_path(thread_id)
        logf.parent.mkdir(parents=True, exist_ok=True)
        header = "# Artifacts Log\n\n"
        prev = logf.read_text(encoding="utf-8", errors="ignore") if logf.exists() else header
        logf.write_text(prev + text + "\n", encoding="utf-8")
        
    def _artifacts_log_info(self, thread_id: str) -> str:
        logf = self.artifacts_log_path(thread_id)
        if logf.exists():
            return logf.read_text(encoding="utf-8", errors="ignore")
        else:
            return ""

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
            ]}
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
        elif ext in {".csv"}:
            return "csv"
        elif ext in {".tsv"}:
            return "tsv"
        elif ext in {".xlsx", ".xls"}:
            return "xlsx"   
        elif ext in {".txt", ".log"}:
            return "txt"
        elif ext in {".md", ".markdown"}:
            return "md"
        elif ext in {".yaml", ".yml"}:
            return "yaml"
        elif ext in {".json"}:
            return "json"
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
            

    async def analyze(self, thread_id:str, user_goal: str, artifacts: List[File], artifact_llm: LLMAdapter, sandbox: CodeSandbox, code_llm: LLMAdapter, eval_llm: LLMAdapter):
        """
        artifacts the analysis pipeline.
        - user_goal: user goal / topic
        - artifacts: list of {"name": ..., "path": ..., "size": ...} (local files)
        - returns: {"report_md": "...", "other_findings": ...}
        """
        # 1) Read/understand artifacts
        try:
            all_artifact_info = self._artifacts_log_info(thread_id)
            if all_artifact_info == "":
                self._append_artifacts_log(
                    thread_id,
                    f"## Artifacts meta"
                )            

            # Read and understand the Artifacts
            for a in artifacts:  
                if f"**{a.name}:**" in all_artifact_info:
                    logger.info(f"Skipping already analyzed artifact {a.name}")
                    continue
                
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
                elif file_type in {"csv", "tsv", "xlsx"}:
                    # artifact path, check inputs dir and outputs dir for the file
                    artifact_local_path = None
                    short_file_path = ""
                    inputs_dir = self._artifacts_dir(thread_id) / self.inputs_dirname
                    outputs_dir = self._artifacts_dir(thread_id) / self.outputs_dirname
                    if (inputs_dir / a.name).exists():
                        artifact_local_path = inputs_dir / a.name
                        short_file_path = str(self.inputs_dirname + "/" + a.name)
                    elif (outputs_dir / a.name).exists():
                        artifact_local_path = outputs_dir / a.name
                        short_file_path = str(self.outputs_dirname + "/" + a.name)
                    else:
                        logger.warning(f"Artifact {a.name} not found in inputs or outputs.")
                        continue

                    req = ExecRequest(
                        code=None,
                        language="python",
                        files_in=[{"name": a.name, "path": str(artifact_local_path)}],
                        timeout_s=60,
                        task=(
                            f"Read and summarize the input file {a.name} to understand its schema and content. "
                            f"Artifact file path: {short_file_path}. "
                            "You should show the all data types, column names and first few rows. So that a model later can use this information to write a summary for this file. "
                        ),
                        use_llm_writer=True,
                        repair_attempts=2,
                    )
                    res = sandbox.exec_cell_raw(
                        thread_id=thread_id,
                        req=req,
                        code_llm=code_llm,
                        eval_llm=eval_llm,
                    )
                    
                    stdout, summary = res.stdout, res.summary
                    
                    artifact_prompt = self.text_analyze_prompt(user_goal, a.name, f"Simple EDA summary:\n{summary}\n\nFull stdout:\n{stdout}")
                    result = artifact_llm.response(artifact_prompt)
                    result = self._extract_markdown(result)
                    self._append_artifacts_log(
                        thread_id,
                        f"### **{a.name}:** \n{result}\n\n"
                    )
                    
            return self._artifacts_log_info(thread_id)

        except Exception as e:
            self._append_artifacts_log(
            thread_id,
            f"## Error reading artifacts: {e}\n\n"
            )
            logger.error(f"Error reading artifacts: {e}")
            