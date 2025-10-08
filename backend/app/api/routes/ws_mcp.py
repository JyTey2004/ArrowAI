# app/agents/ws_mcp.py (enhanced)

from __future__ import annotations
import os, uuid, json, base64, asyncio
from typing import Any, Dict, Optional, List, Callable, Literal
import re

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage

from pydantic import BaseModel, Field, ValidationError

from app.aws.s3_client import S3Client
from app.core.logging import get_logger
from langgraph.checkpoint.memory import MemorySaver
from dotenv import load_dotenv

load_dotenv()  
checkpointer = MemorySaver()
logger = get_logger(__name__)
router = APIRouter()

# -----------------------
# 1) Global deps (lazy init)
# -----------------------
DEFAULT_BUCKET = os.environ.get("MCP_BUCKET", "arrowai")
REGION = os.environ.get("AWS_REGION", "ap-southeast-1")
CODE_AGENT_MCP_WS = os.environ.get("CODE_AGENT_MCP_WS", "http://localhost:5000/mcp/code_agent")
RESEARCH_AGENT_MCP_WS = os.environ.get("RESEARCH_AGENT_MCP_WS", "http://localhost:5001/mcp/research_agent")
ARTIFACT_AGENT_MCP_WS = os.environ.get("ARTIFACT_AGENT_MCP_WS", "http://localhost:5002/mcp/artifacts")
NARRATIVE_AGENT_MCP_WS = os.environ.get("NARRATIVE_AGENT_MCP_WS", "http://localhost:5003/mcp/narrative_agent")

s3c = S3Client(
    bucket_name=DEFAULT_BUCKET,
    region_name=REGION,
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
)
s3c.ensure_bucket(create_if_missing=True)

model = init_chat_model(
    model_provider=os.environ.get("MCP_LLM_PROVIDER", "openai"),
    model=os.environ.get("MCP_LLM_MODEL", "openai:gpt-4.1-mini"),
    temperature=0,
)

_mcp_client: Optional[MultiServerMCPClient] = None
_model_with_tools = None
_tools = None
_tool_metadata: Dict[str, Dict[str, Any]] = {}
_tools_ready = asyncio.Lock()
graph = None  


async def _ensure_tools():
    global _mcp_client, _model_with_tools, _tools, _tool_metadata
    async with _tools_ready:
        if _mcp_client is not None and _model_with_tools is not None and _tools is not None:
            return
        _mcp_client = MultiServerMCPClient(
            {
                "code_agent": {
                    "url": CODE_AGENT_MCP_WS,
                    "transport": "streamable_http",
                },
                "research_agent": {
                    "url": RESEARCH_AGENT_MCP_WS,
                    "transport": "streamable_http",
                },
                "artifact_service": {
                    "url": ARTIFACT_AGENT_MCP_WS,
                    "transport": "streamable_http",
                },
                "narrative_agent": {
                    "url": NARRATIVE_AGENT_MCP_WS,
                    "transport": "streamable_http",
                },
            }
        )
        _tools = await _mcp_client.get_tools()

        logger.info(f"Fetched {_tools} from MCP servers.")

        _tool_metadata = {}
        for tool in _tools:
            name = getattr(tool, "name", None)
            if not name:
                continue
            description = getattr(tool, "description", "") or ""
            tool_meta = getattr(tool, "metadata", {}) or {}
            args_schema = getattr(tool, "args_schema", None)
            _tool_metadata[name] = {
                "description": description,
                "metadata": tool_meta,
                "args_schema": args_schema,
            }

        _model_with_tools = model.bind_tools(_tools)
        logger.info("MCP tools bound over WebSocket.")

# -----------------------
# 2) CEL helpers (S3)
# -----------------------

def _cel_key(base_prefix: str) -> str:
    return f"{base_prefix}/CEL.md"


def _read_cel(base_prefix: str) -> str:
    key = _cel_key(base_prefix)
    try:
        data, _ = s3c.get_bytes(key)
        logger.info(f"Read CEL.md from s3://{s3c.bucket}/{key}, content: {data.decode('utf-8')[:50]}...")
        return data.decode("utf-8")
    except Exception as e:
        logger.error(f"Error reading CEL.md from s3://{s3c.bucket}/{key}: {e}")
        return ""


def _append_cel(base_prefix: str, content: str) -> str:
    prev = _read_cel(base_prefix)
    new = prev + f"\n{content.strip()}\n"
    s3c.put_bytes(key=_cel_key(base_prefix), data=new.encode("utf-8"), content_type="text/markdown")
    return new

TEXT_PREVIEW_EXTS = {".txt", ".md", ".csv", ".tsv", ".json", ".log", ".py", ".ipynb", ".html", ".yaml", ".yml"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp"}

TEXT_PREVIEW_MAX_BYTES = 50_000
TEXT_PREVIEW_SLICE = 8_000

def _prepare_artifact_preview(artifact: dict) -> dict:
    art = dict(artifact)
    uri = art.get("uri") or art.get("path") or ""
    name = art.get("name") or (uri.split("/")[-1] if uri else None)
    if name:
        art["name"] = name
    ext = os.path.splitext(name or "")[1].lower()
    size = art.get("size") or 0

    art.setdefault("type", "document")
    art.setdefault("preview_type", "link")
    art.setdefault("content", "")
    art.setdefault("truncated", False)
    art.setdefault("is_large", False)

    download_url = art.get("download_url")
    if uri.startswith("s3://"):
        try:
            download_url = s3c.presigned_get(uri, expires_in=3600)
            art["download_url"] = download_url
        except Exception as e:
            logger.warning(f"Failed to generate presigned URL for {uri}: {e}")

        if ext in TEXT_PREVIEW_EXTS:
            if size and size > TEXT_PREVIEW_MAX_BYTES:
                art["is_large"] = True
                message = (
                    f"File is {size} bytes which exceeds the inline preview limit. "
                    "Use the download link to view the full content."
                )
                if download_url:
                    message += f"\n[Download the artifact]({download_url})"
                art["content"] = message
                art["preview_type"] = "link"
            else:
                try:
                    data, _ = s3c.get_bytes(uri)
                    preview = data.decode("utf-8", errors="replace")
                    truncated = False
                    if len(preview) > TEXT_PREVIEW_SLICE:
                        preview = preview[:TEXT_PREVIEW_SLICE] + "\n… truncated …"
                        truncated = True
                    art["content"] = preview
                    art["preview_type"] = "text"
                    art["truncated"] = truncated
                except Exception as e:
                    logger.warning(f"Failed to fetch text preview for {uri}: {e}")
                    message = "Failed to fetch preview. Use the download link."
                    if download_url:
                        message += f"\n[Download the artifact]({download_url})"
                    art["content"] = message
                    art["preview_type"] = "link"
        elif ext in IMAGE_EXTS:
            art["preview_type"] = "image"
            art["content"] = download_url
            art.setdefault("type", "image")
        else:
            message = "Preview not available for this file type."
            if download_url:
                message += f"\n[Download the artifact]({download_url})"
            art["content"] = message
            art["preview_type"] = "link"
    else:
        if not art.get("content"):
            art["content"] = "Artifact available. Download to view."
        if ext in TEXT_PREVIEW_EXTS:
            art["preview_type"] = "text"

    if isinstance(art.get("content"), bytes):
        art["content"] = art["content"].decode("utf-8", errors="replace")

    return art

def _parse_tool_payload(message: ToolMessage) -> Optional[dict]:
    content = message.content
    if isinstance(content, dict):
        if "json" in content and isinstance(content["json"], (dict, list)):
            return content["json"]
        return content
    if isinstance(content, list):
        text_chunks = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "json" and isinstance(part.get("json"), (dict, list)):
                    return part["json"]
                if part.get("type") == "text" and isinstance(part.get("text"), str):
                    text_chunks.append(part["text"])
            elif isinstance(part, str):
                text_chunks.append(part)
        if text_chunks:
            candidate = _extract_json("\n".join(text_chunks)) or "\n".join(text_chunks)
            try:
                return json.loads(candidate)
            except Exception:
                return None
    if isinstance(content, str):
        candidate = _extract_json(content)
        try:
            return json.loads(candidate)
        except Exception:
            return None
    return None

def     _extract_json(s: str) -> str:
    """Return the first JSON object found (handles fenced code blocks)."""
    if not s:
        return ""
    # strip fences ```json ... ```
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", s, flags=re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    # fallback: find first {...} block
    brace = re.search(r"\{.*\}", s, flags=re.DOTALL)
    return brace.group(0).strip() if brace else s.strip()


# -----------------------
# 3) System prompts
# -----------------------
CLARIFY_SYSTEM = (
    "You are a careful PM. Decide if the user's request needs clarification to proceed.\n"
    "Clarification is needed if the request is ambiguous, incomplete, or could lead to incorrect execution.\n"
    "If user requests can somewhat be fulfilled, we can proceed without clarification.\n"
    "However, if the task is navigational (e.g., 'explore the data', 'analyze trends', 'build a model'), we can proceed without clarification.\n"
    "If clarification is needed, ask ONE concise question." 
    "If not, answer exactly 'NO_CLARIFICATION_NEEDED'."
)


TODO_SYSTEM = (
    "You are a delivery lead.\n"
    "Summarize the user's task into a deliverable goal at the top and a concise TODO list below.\n"
    "Break the task into a concise TODO list (markdown) of concrete, executable steps and deliverables.\n"
    "Each step should be a small, manageable action, with clear inputs and outputs. That can be done within a single cell of code.\n"
    "Be specific about each todo, e.g., if a file is needed, specify the exact filename and what should be in it.\n"
    "You may read CEL.md for context. Which will be the primary source of truth for previous tasks.\n"
    "If user requires a file, specify the exact filename, file format, and what should be in it.\n"
    "Each todo should only contain one action and one output.\n"
    "You may assume all files are in S3 and can be read from there, hence theres no need to mention downloading/uploading.\n"
    "Generate markdown only (no fences, no commentary)."
)


EXECUTE_SYSTEM = (
    "You are a project manager at ArrowAI, overseeing task execution.\n"
    "You specialize in solving the user's request with a multi-step approach.\n"
    "Use tools available to you to solve the user's request efficiently and proactively.\n\n"
    
    "You have access to the following tools:\n"
    "- Code Agent: Completes task that requires code execution.\n"
    "- Research Agent: Completes tasks that require web search and information gathering.\n"
    "- Artifact Agent: Understands and manages artifacts (files, documents, etc.) produced during execution.\n"
    "- Narrative Agent: Crafts narratives, reports, and presentations based on gathered information and artifacts.\n\n"
    "Your goal is to complete the user's request by using these tools effectively.\n"
    "Start by understanding the complete situation before proposing solutions, ask follow up questions if you do not understand.\n"
    
    "Response Framework:\n"
    "  1. Identify the SINGLE next step to take towards completing the user's request.\n"
    "  2. Gather any necessary information or resources to support this step.\n"
    "  3. Choose the MOST APPROPRIATE tool to execute this step.\n"
    "  4. Provide the most DETAILED and SPECIFIC description of this step to the tool schema.\n"
    "  5. Output MUST contain a single tool call with the chosen tool and its arguments, unless the task is complete.\n"
    
    "Guidelines:\n"
    "- When multiple tools are possible, choose the one that is most likely to succeed and is the most efficient.\n"
    "- All tool calls are synchronous. If you call the same tool multiple times in parallel, be aware of potential race conditions. For example, if you output 2 tool calls for code execution, they will run independently and give outputs in an unpredictable order.\n"
    "- You should call and execute code once per output. Do not make multiple code call tool calls unless they are completely independent.\n"
    "- If step requires other files, assume they are in S3 and can be read from there, hence theres no need to mention downloading/uploading.\n"
    "- Always validate and sanitize inputs to tools to prevent injection attacks or unexpected behavior.\n"
    "- If you believe the user's request is fully complete, just output what you delivered instead of tool calls.\n"
)

EXECUTE_SUMMARY_SYSTEM = (
    "You are an Quality Assurance (QA) specialist. Produce a STRICT JSON object that matches this schema:\n"
    "ExecSummaryOutput = { summary: str, artifacts: [{name: str, uri: str, description: str, size?: int}] }\n"
    "\n"
    "Inputs you may rely on:\n"
    "- Context summary (if provided): A summary of all tool calls and execution steps\n"
    "- CEL.md (An overview of the user's task and context)\n"
    "- Tool outputs: Current tool outputs\n"
    "\n"
    
    "Response Framework:\n"
    "   1. Identify the most critical points from the context and tool outputs.\n"
    "   2. From the critical points, derive a consise summary of what was done.\n"
    "   3. This summary should contain everything that happened so the user will know what to do next.\n"
    "   4. Identify and list all artifacts (files, reports, datasets) that were produced during execution.\n"
    
    "Guidelines:\n"
    "1) Return ONLY the JSON object (no prose, no code fences, no trailing commas).\n"
    "2) summary: Markdown text (no code fences) that fully documents what happened in a short but comprehensive manner.\n"
    "3) artifacts: derive ONLY from confirmed file/manifests in Tool output. One entry per file.\n"
    "   - name: human-friendly filename or title\n"
    "   - uri: full path (s3://bucket/key or http(s)://...)\n"
    "   - description: a brief description of the artifact\n"
    "   - size: include if known (bytes); omit if unknown.\n"
    "   - Deduplicate; list only files that actually exist per the sources.\n"
    "4) Prefer clear bullet points and short paragraphs; keep it compact but complete (no hard char limit).\n"
)


RESPONDER_SYSTEM = (
    "You are a precise analyst. You can read CEL.md and see a provided list of artifacts.\n"
    "Your job: write a clear, concise reply to the user about what happened.\n"
    "\n"
    "Grounding:\n"
    "- Use ONLY facts from CEL.md and the provided artifacts list. Never invent details.\n"
    "- If a fact isn't in those sources, say you don't have that info.\n"
    "- Please output relevant artifacts as a markdown list with links/paths to support your response.\n"
    "\n"
    "Output format (markdown, no code fences):\n"
    "Just answer the user with the below\n"
    "What was done and key results (with concrete numbers/dates when available).\n"
    "Bullet list of ONLY relevant artifacts. If an item has an HTTP(S) URL, link it. If it has an s3:// URI, show it as inline code. If only a relative path is given, show it as inline code.\n"
    "\n"
    "Rules:\n"
    "1) Be concise and user-facing; avoid internal jargon and raw logs.\n"
    "2) Do not restate the entire CEL.md; summarize the essentials.\n"
    "3) If the task is fully done, make that explicit in the Summary.\n"
    "4) If the user asked a question, answer it directly using CEL.md/artifacts first, then include the sections above.\n"
)


# -----------------------
# 4) State type & emit helper
# -----------------------
class MCPState(dict):
    """Conversation + execution state passed through the graph."""
    messages: List[dict]
    step_idx: int
    max_steps: int
    done: bool
    todo: Optional[str]
    awaiting_todo_feedback: bool
    resume_from: Optional[str]
    need_clarification: bool
    clarifying_question: Optional[str]
    artifacts: List[dict]
    context_sumary: Optional[str]

class Artifact(BaseModel):
    name: str
    uri: str = Field(..., description="Full URI of the artifact, e.g., s3://bucket/key or http(s)://...")
    size: Optional[int] = None

class ExecSummaryOutput(BaseModel):
    summary: str          # markdown text (no fences)
    artifacts: list[Artifact] = Field(
        default_factory=list,
        description="A list of artifacts produced by the execution"
    )

# --------------------
# 5) Graph nodes
# -----------------------
async def clarify_node(state: MCPState, config: RunnableConfig):
    try:
        emit = config["configurable"]["emit"]
        thread_id = config["configurable"]["thread_id"]
        exec_ctx = config["configurable"]["exec_ctx"]
        base_prefix = exec_ctx["base_prefix"]
        
        emit({"event": "node", "name": "clarify"})

        resume_target = state.get("resume_from")

        if resume_target == "execute":
            logger.info(f"Clarify node for thread_id={thread_id} skipping clarification to resume execution.")
            state["resume_from"] = None
            return {
                "need_clarification": False,
                "clarifying_question": None,
            }
        if resume_target == "todo":
            logger.info(f"Clarify node for thread_id={thread_id} resuming directly at TODO generation.")
            state["resume_from"] = None
            return {
                "need_clarification": False,
                "clarifying_question": None,
            }
        
        if state.get("need_clarification") == False:
            # This is the first user message
            message = f"""# Context for:
- Thread ID: {thread_id}
- User Message: {state['messages'][-1].content}
                """
        else:
            # This is a follow-up after clarification
            message = f"""
                    - Previous Clarifying Question: {state.get('clarifying_question')}
                    - User Clarification: {state['messages'][-1].content}
                """


        cel_snip = _read_cel(base_prefix)

        prompt = f"CEL.md (context):\n{cel_snip}\n\nMessages:\n{state['messages']}\n\nDo we need clarification?"

        logger.info(f"Clarify node for thread_id={thread_id} checking clarification with prompt:\n{prompt}\n--- end prompt ---\n\n")

        user_plus = [
            {"role": "system", "content": CLARIFY_SYSTEM},
            {"role": "user", "content": prompt}
        ]
        resp = await model.ainvoke(user_plus)
        out = (resp.content or "").strip()
        need = out.upper() != "NO_CLARIFICATION_NEEDED"
        
        logger.info(f"Clarify node for thread_id={thread_id} decided need_clarification={need} with output:\n{out}\n--- end output ---\n\n")


        # No clarification: log and proceed
        cel_text = _append_cel(base_prefix, message)
        emit({"event": "cel", "content": cel_text})

        
        if need:
            # Return ALL fields needed by downstream routing/node
            return {
                "need_clarification": True,
                "clarifying_question": out,
            }
            

        return {
            "need_clarification": False,
            "clarifying_question": None,
        }
    except Exception as e:
        logger.exception(f"Clarify node error: {e}")
        raise


async def todo_node(state: MCPState, config: RunnableConfig):
    try:
        emit = config["configurable"]["emit"]
        thread_id = config["configurable"]["thread_id"]
        exec_ctx = config["configurable"]["exec_ctx"]
        base_prefix = exec_ctx["base_prefix"]
        await emit({"event": "node", "name": "write_todos"})
        
        cel_snip = _read_cel(base_prefix)
        
        prompt = f"CEL.md (context):\n{cel_snip}\n\nMessages:\n{state['messages']}\n\nCreate a concise TODO list."
        
        logger.info(f"Todo node for thread_id={thread_id} generating todo with prompt:\n{prompt}\n--- end prompt ---\n\n")

        resp = await model.ainvoke([
            {"role": "system", "content": TODO_SYSTEM},
            {"role": "user", "content": prompt}
        ])
        todo_md = resp.content or "- [ ] Step 1\n- [ ] Step 2"
        
        logger.info(f"Todo node for thread_id={thread_id} produced todo:\n{todo_md}\n--- end todo ---\n\n")
        await emit({"event": "todos", "markdown": todo_md, "requires_feedback": True})
        
        todo_message = f"""## Task Breakdown:
{todo_md}
        """

        # Only log when user accepts the todo
        if state.get("awaiting_todo_feedback"):
            state["resume_from"] = "execute"
            cel_text = _append_cel(base_prefix, todo_message)
            emit({"event": "cel", "content": cel_text})

        return {
            "todo": todo_md,
        }
    except Exception as e:
        logger.exception(f"Todo node error: {e}")
        raise


async def await_todo_feedback_node(state: MCPState, config: RunnableConfig):
    try:
        emit = config["configurable"]["emit"]
        thread_id = config["configurable"]["thread_id"]

        await emit({"event": "node", "name": "await_todo_feedback"})
        logger.info(f"Awaiting TODO feedback for thread_id={thread_id}.")

        return {
            "awaiting_todo_feedback": True,
        }
    except Exception as e:
        logger.exception(f"Await TODO feedback node error: {e}")
        raise

async def execute_node(state: MCPState, config: RunnableConfig):
    try:
        emit = config["configurable"]["emit"]
        thread_id = config["configurable"]["thread_id"]
        exec_ctx = config["configurable"]["exec_ctx"]
        base_prefix = exec_ctx["base_prefix"]

        state["awaiting_todo_feedback"] = False
        state["resume_from"] = None
        
        emit({"event": "node", "name": "execute", "step": state.get("step_idx", 0)})
        
        cel_snip = _read_cel(base_prefix)

        context_summary = state.get("context_summary") or ""

        all_messages = state["messages"]

        tool_messages = [m for m in all_messages if isinstance(m, ToolMessage)]
        
        tool_content = []
        new_artifacts = []

        prev_tool_count = len(tool_messages)

        # If last message is a ToolMessage, we pop it and summarize its results first
        if tool_messages:

            for tm in tool_messages:
                content = tm.content or ""
                tool_content.append(f"Tool: {tm.name}\nOutput:\n{content}\n")
            
            logger.info(f"Execute node for thread_id={thread_id}, step_idx={state.get('step_idx',0)} , tool messages:\n{tool_messages}\n--- end tool outputs ---\n\n")

            summarize_prompt = [
                {"role": "system", "content": EXECUTE_SUMMARY_SYSTEM},
            ]
            
            # Context summary
            if context_summary:
                summarize_prompt.append({"role": "user", "content": f"Context Summary:\n{context_summary}\n"})
                
            summarize_prompt.append({"role": "user", "content": f"CEL.md (context):\n{cel_snip}"})
            summarize_prompt.append({"role": "user", "content": f"Tool Outputs:\n{tool_content}"})

            resp = await model.ainvoke(summarize_prompt)

            raw = (resp.content or "").strip()
            json_text = _extract_json(raw)

            try:
                payload = json.loads(json_text)
            except json.JSONDecodeError as e:
                # Fail closed with a minimal fallback summary so the run can continue
                fallback = {
                    "summary": "Execution completed, but the summarizer returned invalid JSON. See CEL.md and logs for details.\n\nErrors: JSONDecodeError in EXECUTE_SUMMARY_SYSTEM.",
                    "artifacts": []
                }
                payload = fallback
                
            try:
                # Optional: import your models
                # from app.models.exec_summary import ExecSummaryOutput, Artifact
                summary_obj = ExecSummaryOutput(**payload)
            except ValidationError as ve:
                # Second-chance fallback if keys/types are off
                summary_obj = ExecSummaryOutput(
                    summary=payload.get("summary", "Execution complete. (Schema validation failed; see logs.)"),
                    artifacts=[]
                )
                logger.warning(f"ExecSummaryOutput validation failed: {ve}")

            # Update the context summary in state - we replace as this the latest summary will also contain previous summaries
            context_summary = summary_obj.summary

            # Log and keep artifacts in state for downstream tools/UI
            logger.info(
                "Execute summary for thread_id=%s, step_idx=%s:\n%s\n--- end summary ---\nArtifacts: %s",
                thread_id, state.get("step_idx", 0), summary_obj.summary, summary_obj.artifacts
            )

            # Remove verbose ToolMessages before adding the assistant summary
            all_messages = [m for m in all_messages if not isinstance(m, ToolMessage)]
            all_messages.append(AIMessage(content=summary_obj.summary))
            existing_uris = {a.get("uri") for a in state.get("artifacts", []) if a.get("uri")}
            for summary_art in summary_obj.artifacts:
                if summary_art.uri and summary_art.uri not in existing_uris:
                    art_dict = _prepare_artifact_preview(summary_art.dict())
                    state["artifacts"].append(art_dict)
                    new_artifacts.append(art_dict)
                    existing_uris.add(summary_art.uri)
        
        logger.info(f"Context summary for thread_id={thread_id}, step_idx={state.get('step_idx',0)}:\n{context_summary}\n--- end context summary ---\n\n")

        # Prepend system for policy
        prompt = [
            {"role": "system", "content": EXECUTE_SYSTEM},
            {"role": "user", "content": f"An overview of the all previous tool calls and execution steps:\n{context_summary}"},
            {"role": "user", "content": f"CEL.md (context):\n{cel_snip}"},
            {"role": "user", "content": f"Artifacts:\n{state.get('artifacts', [])}"},
        ]
        
        if tool_content:
            prompt.append({"role": "user", "content": f"Last Tool outputs:\n{tool_content}"})
        
        resp = await _model_with_tools.ainvoke(prompt)
        
        logger.info(f"Execute node for thread_id={thread_id}, step_idx={state.get('step_idx',0)} got response:\n{resp}\n--- end response ---\n\n")
        
        all_messages.append(resp)

        for tool_call in resp.tool_calls or []:
            tool_name = tool_call.get("name")
            logger.info(f"Execute node for thread_id={thread_id}, step_idx={state.get('step_idx',0)} invoking tool call: {tool_call}")
            thought_payload = {
                "tool": tool_name,
                "args": tool_call.get("args", {}),
            }

            tool_info = _tool_metadata.get(tool_name or "", {})
            description = tool_info.get("description") or "No description provided."
            raw_metadata = tool_info.get("metadata") or {}
            if not isinstance(raw_metadata, dict):
                raw_metadata = {}
            try:
                metadata = json.loads(json.dumps(raw_metadata, default=str))
            except Exception:
                metadata = {}
            server_name = metadata.get("server") or metadata.get("mcp_server")

            await emit({
                "event": "tool.call",
                "tool": tool_name,
                "description": description,
                "args": tool_call.get("args", {}),
                "server": server_name,
                "metadata": metadata,
            })
            await emit({"event": "thought", "text": f"Decided to use tool: {tool_name}"})
            await emit({"event": "sandbox.stdout", "text": f"Using tool:{tool_name} with args {json.dumps(tool_call.get('args', {}), indent=2)}\n"})

        emitted_artifact_uris: set[str] = set()
        updated_tool_messages = [m for m in all_messages if isinstance(m, ToolMessage)]
        new_tool_messages = updated_tool_messages[prev_tool_count:]

        for tm in new_tool_messages:
            payload = _parse_tool_payload(tm) or {}
            for step in payload.get("steps", []):
                step_id = step.get("step")
                status = "success" if step.get("ok", True) else "error"
                status_payload = {
                    "event": "sandbox.status",
                    "step": step_id,
                    "status": status,
                    "plan": step.get("plan"),
                    "summary": step.get("summary"),
                }
                await emit(status_payload)

                code_obj = step.get("code") or {}
                code_text = code_obj.get("text") or ""
                if code_text.strip():
                    filename = code_obj.get("name") or (f"step_{step_id}.py" if step_id is not None else None)
                    await emit({
                        "event": "code",
                        "text": code_text,
                        "filename": filename,
                    })

                step_artifacts = step.get("artifacts") or []
                if step_artifacts:
                    enriched_step_artifacts = []
                    for artifact_item in step_artifacts:
                        prepared = _prepare_artifact_preview(artifact_item)
                        if step_id is not None:
                            prepared["step"] = step_id
                        enriched_step_artifacts.append(prepared)
                        uri = prepared.get("uri") or prepared.get("path")
                        if uri:
                            emitted_artifact_uris.add(uri)
                    await emit({"event": "sandbox.artifacts", "items": enriched_step_artifacts})

        if new_artifacts:
            enriched = []
            for art in new_artifacts:
                prepared = _prepare_artifact_preview(art)
                uri = prepared.get("uri") or prepared.get("path")
                if uri and uri in emitted_artifact_uris:
                    continue
                enriched.append(prepared)
            if enriched:
                await emit({"event": "sandbox.artifacts", "items": enriched})

        return {
            "messages": all_messages,
            "context_summary": context_summary,
            "step_idx": state.get("step_idx", 0) + 1,
        }
    except Exception as e:
        logger.exception(f"Execute node error: {e}")
        raise


async def reply_node(state: MCPState, config: RunnableConfig):
    try:
        emit = config["configurable"]["emit"]
        thread_id = config["configurable"]["thread_id"]
        exec_ctx = config["configurable"]["exec_ctx"]
        base_prefix = exec_ctx["base_prefix"]
        emit({"event": "node", "name": "respond"})

        # If clarification is needed, ONLY ask the question and stop here
        if state.get("need_clarification") and state.get("clarifying_question"):
            q = state["clarifying_question"]
            emit({"event": "clarify", "question": q})
            messages = state["messages"].append({"role": "assistant", "content": q})
            return {
                "messages": messages,
            }
            
        cel_snip = _read_cel(base_prefix)

        # Otherwise, produce the normal answer
        artifacts = state.get("artifacts", [])
        
        prompt = f"CEL.md (context):\n{cel_snip}\n\nMessages:\n{state['messages']}\n\nArtifacts:\n{artifacts}\n\nProvide a concise answer."
        
        logger.info(f"Reply node for thread_id={thread_id} generating answer with prompt:\n{prompt}\n--- end prompt ---\n\n")
        
        resp = await model.ainvoke([
            {"role": "system", "content": RESPONDER_SYSTEM},
            {"role": "user", "content": prompt}
        ])
        answer_text = resp.content or "Here is the summary of what was done."
    
        state["messages"].append(AIMessage(content=answer_text))
        
        # Extract all s3:// in answer_text as artifacts (if not already present)
        s3_uris = re.findall(r"s3://[^\s`]+", answer_text) # Get all s3://bucket/key patterns
        for uri in s3_uris:
            # update the s3_uris to presigned URLs
            presigned = s3c.presigned_get(
                key=uri,
                expires_in=3600
            )
            answer_text = answer_text.replace(uri, presigned)

        emit({"event": "answer", "text": answer_text})
        if artifacts:
            emit({"event": "answer.artifacts", "items": artifacts})

        # Now that we've answered, clear clarification flags via returned updates
        return {
            "messages": state["messages"],
            "need_clarification": False,
            "clarifying_question": None,
        }
    except Exception as e:
        logger.exception(f"Reply node error: {e}")
        raise

def route_after_clarify(state: MCPState) -> Literal["todo", "reply", "execute"]:
    if state.get("resume_from") == "execute":
        return "execute"
    return "reply" if state.get("need_clarification") and state.get("clarifying_question") else "todo"

async def route_after_execute(state: MCPState, config: RunnableConfig) -> Literal["tools", "reply"]:
    try:
        emit = config["configurable"]["emit"]
        if state.get("done"):
            return "reply"
        
        messages = state["messages"]
        
        # logger.info(f"Route after execute checking messages for thread_id={config['configurable']['thread_id']}, step_idx={state.get('step_idx',0)}:\n{messages}\n--- end messages ---\n\n")
        
        last_message = messages[-1]
        
        if isinstance(last_message, AIMessage):
            if last_message.tool_calls: 
                return "tools"
        
        
        # If no tool calls, we assume done
        exec_ctx = config["configurable"]["exec_ctx"]
        base_prefix = exec_ctx["base_prefix"]
        context_summary = state.get("context_summary") or ""
        if context_summary:
            cel_text = _append_cel(base_prefix, f"## Execution Summary:\n{context_summary}\n")
            emit({"event": "cel", "content": cel_text})
            logger.info(f"Route after execute appended context summary to CEL.md for thread_id={config['configurable']['thread_id']}, step_idx={state.get('step_idx',0)}:\n{context_summary}\n--- end summary ---\n\n")
    
        return "reply"

    except Exception as e:
        logger.exception(f"Route after execute error: {e}")
        raise


# -----------------------
# 6) Build graph once
# -----------------------
def _build_graph():
    global graph
    if graph is not None:
        return graph
    _builder = StateGraph(MCPState)
    _builder.add_node("clarify", clarify_node)
    _builder.add_node("todo", todo_node)
    _builder.add_node("await_todo_feedback", await_todo_feedback_node)
    _builder.add_node("execute", execute_node)
    _builder.add_node("tools", ToolNode(tools=_tools))
    _builder.add_node("reply", reply_node)

    _builder.add_edge(START, "clarify")
    _builder.add_conditional_edges("clarify", route_after_clarify, {"todo": "todo", "reply": "reply", "execute": "execute"})
    _builder.add_edge("todo", "await_todo_feedback")
    _builder.add_edge("await_todo_feedback", END)
    _builder.add_conditional_edges("execute", route_after_execute, {"tools": "tools", "reply": "reply"})
    _builder.add_edge("tools", "execute")
    _builder.add_edge("reply", END)

    graph = _builder.compile(checkpointer=checkpointer)



# -----------------------
# 7) WS helpers
# -----------------------

def _safe_filename(name: str) -> str:
    return os.path.basename(name).replace("\\", "_").replace("/", "_")

async def _upload_ws_files(
    files: List[Dict[str, Any]] | None,
    bucket: str,
    base_prefix: str,
) -> List[Dict[str, str]]:
    """
    files: [{name, content_type, b64}]  (UI should send base64 of the file)
    Returns: [{"name","uri","content_type","size"}]
    """
    if not files:
        return []
    out = []
    for f in files:
        name = _safe_filename(f.get("name") or uuid.uuid4().hex)
        ctype = f.get("content_type") or "application/octet-stream"
        key = f"{base_prefix}/uploads/{name}"
        if f.get("b64"):
            data = base64.b64decode(f["b64"])
        else:
            data = f.get("content", b"").encode("utf-8")
        man = s3c.put_bytes(key=key, data=data, content_type=ctype).to_dict()
        out.append({"name": name, "uri": man["uri"], "content_type": ctype, "size": str(man["size"])})
    return out


# -----------------------
# 8) WebSocket endpoint
# -----------------------    

@router.websocket("/ws/mcp_graph")
async def ws_mcp_graph(
    ws: WebSocket,
    thread_id: Optional[str] = Query(default=None),
):
    """
    Client → Server JSON per turn:
      {
        "type": "user_message",
        "text": "...",
        "files": [{"name":"file.csv","content_type":"text/csv","b64":"..."}] // optional
      }
    """
    await ws.accept()

    def emitter(payload: dict):
        # Fire-and-forget emitter used by nodes
        try:
            return asyncio.create_task(ws.send_json(payload))
        except RuntimeError:
            # Fallback if loop not running
            return None

    try:
        await _ensure_tools()
        # Per-connection run id + prefix
        tid = thread_id or uuid.uuid4().hex
        base_prefix = f"threads/{tid}"
        
        # Conversation state for this socket
        state: MCPState = MCPState(
            messages=[],
            step_idx=0,
            max_steps=20,
            done=False,
            todo=None,
            awaiting_todo_feedback=False,
            resume_from=None,
            need_clarification=False,
            clarifying_question=None,
            artifacts=[],
        )
        
        initial_cel = _read_cel(base_prefix)
        emitter({"event": "cel", "content": initial_cel})
        
        while True:
            raw = await ws.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"event": "error", "detail": "Malformed JSON"})
                continue

            message_type = payload.get("type")

            config = {
                "configurable": {
                    "thread_id": tid,
                    "emit": emitter,
                    "exec_ctx": {"bucket": DEFAULT_BUCKET, "base_prefix": base_prefix},
                }
            }

            if message_type == "user_message":
                if state.get("awaiting_todo_feedback"):
                    await ws.send_json({"event": "error", "detail": "Awaiting TODO approval. Approve or update the TODO list to continue."})
                    continue

                user_text: str = (payload.get("text") or "").strip()
                files = payload.get("files", []) or []
                uploaded = await _upload_ws_files(files, DEFAULT_BUCKET, base_prefix)
                files_note = ""
                if uploaded:
                    bullet = "\n".join([f"- {u['name']}: {u['uri']}" for u in uploaded]) # Do not need full s3:// path as base_prefix has it
                    files_note = f"\nUploaded files (S3 RELATIVE PATHS):\n{bullet}."

                state["artifacts"] = uploaded

                logger.info(f"WS MCP graph thread_id={tid} got user message: {user_text}{files_note}")

                state["messages"].append(HumanMessage(content=user_text + files_note))

                result = await graph.ainvoke(state, config=config)
                logger.info(f"WS MCP graph thread_id={tid} node returned updates: {result}")
                if result is not None:
                    state = MCPState(result)

            elif message_type == "todo_feedback":
                decision = payload.get("decision")
                comment = (payload.get("comment") or "").strip()
                updated_markdown = (payload.get("markdown") or "").strip()

                if not state.get("awaiting_todo_feedback"):
                    await ws.send_json({"event": "error", "detail": "No TODO review pending for this thread."})
                    continue

                if decision not in {"approve", "update"}:
                    await ws.send_json({"event": "error", "detail": "decision must be 'approve' or 'update'."})
                    continue

                if decision == "update":
                    if not updated_markdown and not comment:
                        await ws.send_json({"event": "error", "detail": "Provide feedback or TODO guidance when requesting changes."})
                        continue

                    feedback_messages: list[str] = []

                    if updated_markdown:
                        state["todo"] = updated_markdown
                        feedback_messages.append(f"User provided TODO draft:\n{updated_markdown}")
                        cel_text = _append_cel(base_prefix, f"## User Updated TODO:\n{updated_markdown}\n")
                        emitter({"event": "cel", "content": cel_text})

                    if comment:
                        feedback_messages.append(f"User feedback on TODO plan:\n{comment}")
                        cel_text = _append_cel(base_prefix, f"## TODO Update Comment:\n{comment}\n")
                        emitter({"event": "cel", "content": cel_text})

                    if feedback_messages:
                        state["messages"].append(HumanMessage(content="\n\n".join(feedback_messages)))

                    state["awaiting_todo_feedback"] = False
                    state["resume_from"] = "todo"

                    await ws.send_json({"event": "todos.status", "status": "updating"})
                    logger.info(f"WS MCP graph thread_id={tid} received TODO feedback; regenerating plan.")

                    try:
                        result = await graph.ainvoke(state, config=config)
                        logger.info(f"WS MCP graph thread_id={tid} regenerated TODO after feedback: {result}")
                        if result is not None:
                            state = MCPState(result)
                    except Exception:
                        logger.exception("Failed to regenerate TODO after user feedback")
                        await ws.send_json({"event": "error", "detail": "Failed to regenerate TODO plan."})
                        state["awaiting_todo_feedback"] = True
                        state["resume_from"] = None
                    continue

                # decision == approve
                approved_markdown = updated_markdown or state.get("todo") or ""
                if approved_markdown:
                    state["todo"] = approved_markdown
                    cel_text = _append_cel(base_prefix, f"## Approved TODO:\n{approved_markdown}\n")
                    emitter({"event": "cel", "content": cel_text})

                approval_message = "User approved the TODO plan."
                if comment:
                    approval_message += f"\nComment: {comment}"

                state["awaiting_todo_feedback"] = False
                state["resume_from"] = "execute"
                state["messages"].append(HumanMessage(content=approval_message))
                if comment:
                    cel_text = _append_cel(base_prefix, f"## TODO Approval Comment:\n{comment}\n")
                    emitter({"event": "cel", "content": cel_text})

                if approved_markdown:
                    await ws.send_json({"event": "todos", "markdown": approved_markdown, "requires_feedback": False, "source": "approved"})
                await ws.send_json({"event": "todos.status", "status": "approved"})
                logger.info(f"WS MCP graph thread_id={tid} TODO plan approved by user.")

                result = await graph.ainvoke(state, config=config)
                logger.info(f"WS MCP graph thread_id={tid} resumed after TODO approval: {result}")
                if result is not None:
                    state = MCPState(result)

            else:
                await ws.send_json({"event": "error", "detail": "Unsupported message type"})

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.exception("WebSocket error: %s", e)
        try:
            await ws.send_json({"event": "error", "detail": str(e)})
        finally:
            await ws.close()
