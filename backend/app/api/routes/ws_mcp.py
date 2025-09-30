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
SANDBOX_MCP_WS = os.environ.get("SANDBOX_MCP_WS", "http://localhost:8787/mcp")

s3c = S3Client(
    bucket_name=DEFAULT_BUCKET,
    region_name=REGION,
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
)
s3c.ensure_bucket(create_if_missing=True)

model = init_chat_model(
    model="openai:gpt-4.1-mini",
    temperature=0,
)

_mcp_client: Optional[MultiServerMCPClient] = None
_model_with_tools = None
_tools = None
_tools_ready = asyncio.Lock()
graph = None  


async def _ensure_tools():
    global _mcp_client, _model_with_tools, _tools
    async with _tools_ready:
        if _mcp_client is not None and _model_with_tools is not None and _tools is not None:
            return
        _mcp_client = MultiServerMCPClient(
            {
                "sandbox": {
                    "url": SANDBOX_MCP_WS,
                    "transport": "streamable_http",
                },
            }
        )
        _tools = await _mcp_client.get_tools()

        logger.info(f"Fetched {_tools} from MCP servers.")

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


def _append_cel(base_prefix: str, content: str) -> None:
    prev = _read_cel(base_prefix)
    new = prev + f"\n{content.strip()}\n"
    s3c.put_bytes(key=_cel_key(base_prefix), data=new.encode("utf-8"), content_type="text/markdown")

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
    "You are a senior consultant. You should break down the TODO in CEL.md into manageable 3-7 steps with tasks for tools to solve.\n"
    "You have a maximum of 7 steps to complete the TODO.\n"
    "Try not to be too granular; if a step is trivial, combine it with another. Try to accomplish a TODO in CEL.md in one step.\n"
    "An example of a trivial step is: just exploring a dataset, or loading a file, or printing the first few lines of a dataframe.\n"
    "Instead, you should combine it with the next step that actually does something useful.\n"
    "Read the Tool documentation carefully; it will help you understand the capabilities and limitations of each tool."
    "You should decide the SINGLE next step to execute now. After this task you will be looped back until the task is complete, so break it down.\n"
    "Your task is to read the CEL.md file and:\n"
        "1. Determine what should be done in this step, be specific about what should be done when writing the filling the Tool schema.\n"
        "2. Correctly fill in the schema as specific as possible for the tool by reading the tool's documentation\n"
        "3. All files are uploaded to S3, so if a tool requires a file argument, pass it the FULL S3 path\n"
        "4. Specify if output files are expected\n"
    "Note:\n"
    "- All tool calls are synchronous. If you call the same tool multiple times in parallel, be aware of potential race conditions. For example, if you output 2 tool calls for code execution, they will run independently and give outputs in an unpredictable order.\n"
    "- You should call and execute code once per output. Do not make multiple code call tool calls unless they are completely independent.\n"
    "- Always validate and sanitize inputs to tools to prevent injection attacks or unexpected behavior.\n"
    "If you believe the user's request is fully complete, just output what you delivered instead of tool calls.\n"
)

EXECUTE_SUMMARY_SYSTEM = (
    "You are an execution summarizer. Produce a STRICT JSON object that matches this schema:\n"
    "ExecSummaryOutput = { summary: str, artifacts: [{name: str, path: str, size?: int}] }\n"
    "\n"
    "Inputs you may rely on:\n"
    "- CEL.md (task, steps taken, deliverables)\n"
    "- TODO list (what was planned)\n"
    "- Tool outputs (stdout/stderr), manifests, and file lists\n"
    "- The user's original request (first section of CEL.md)\n"
    "\n"
    "Authoring rules:\n"
    "1) Return ONLY the JSON object (no prose, no code fences, no trailing commas).\n"
    "2) summary: Markdown text (no code fences) that fully documents what happened in bullet points in the below format:\n"
    "   - TASK: <WHAT WAS DONE>\n"
    "   - RESULTS: <KEY FINDINGS, METRICS, INSIGHTS>\n"
    "   - ARTIFACTS: <FILES PRODUCED, IF ANY>\n"
    "   - FEEDBACK: <FEEDBACK BASED ON TOOL OUTPUTS>\n"
    "   - ISSUES: <ANY ERRORS OR BLOCKERS, IF ANY>\n"
    "3) artifacts: derive ONLY from confirmed file/manifests in sources. One entry per file.\n"
    "   - name: human-friendly filename or title\n"
    "   - uri: full path (s3://bucket/key or http(s)://...)\n"
    "   - size: include if known (bytes); omit if unknown.\n"
    "   - Deduplicate; list only files that actually exist per the sources.\n"
    "4) If all items in todo list are FULLY complete (No/Negligible Feedback or Issues), begin the summary with 'USER_OBJECTIVE_COMPLETE'.\n"
    "5) Prefer clear bullet points and short paragraphs; keep it compact but complete (no hard char limit).\n"
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
    need_clarification: bool
    clarifying_question: Optional[str]
    artifacts: List[dict]
    
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
        _append_cel(base_prefix, message)

        
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
        emit({"event": "node", "name": "write_todos"})
        
        cel_snip = _read_cel(base_prefix)
        
        prompt = f"CEL.md (context):\n{cel_snip}\n\nMessages:\n{state['messages']}\n\nCreate a concise TODO list."
        
        logger.info(f"Todo node for thread_id={thread_id} generating todo with prompt:\n{prompt}\n--- end prompt ---\n\n")

        resp = await model.ainvoke([
            {"role": "system", "content": TODO_SYSTEM},
            {"role": "user", "content": prompt}
        ])
        todo_md = resp.content or "- [ ] Step 1\n- [ ] Step 2"
        
        logger.info(f"Todo node for thread_id={thread_id} produced todo:\n{todo_md}\n--- end todo ---\n\n")
        
        todo_message = f"""## Task Breakdown:
{todo_md}
        """

        _append_cel(base_prefix, todo_message)

        return {
            "todo": todo_md,
        }
    except Exception as e:
        logger.exception(f"Todo node error: {e}")
        raise

async def execute_node(state: MCPState, config: RunnableConfig):
    try:
        emit = config["configurable"]["emit"]
        thread_id = config["configurable"]["thread_id"]
        exec_ctx = config["configurable"]["exec_ctx"]
        base_prefix = exec_ctx["base_prefix"]
        
        emit({"event": "node", "name": "execute", "step": state.get("step_idx", 0)})
        
        cel_snip = _read_cel(base_prefix)
        
        all_messages = state["messages"]

        tool_messages = [m for m in all_messages if isinstance(m, ToolMessage)]

        # If last message is a ToolMessage, we pop it and summarize its results first
        if tool_messages:

            tool_content = [m.content for m in tool_messages]
            
            logger.info(f"Execute node for thread_id={thread_id}, step_idx={state.get('step_idx',0)} , tool messages:\n{tool_messages}\n--- end tool outputs ---\n\n")
            
            todo = state.get("todo", "")

            resp = await model.ainvoke([
                {"role": "system", "content": EXECUTE_SUMMARY_SYSTEM},
                {"role": "user", "content": f"Respect the User Message and Todo List. CEL.md (context):\n{cel_snip[-500:]}"}, # last 500 chars
                {"role": "user", "content": f"Todo List:\n{todo}"},
                {"role": "user", "content": f"Tool outputs:\n{tool_content}"},
            ])

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
            
            # Write only the markdown summary to CEL.md
            _append_cel(base_prefix, f"### Step {state.get('step_idx',0)} Summary (Based on Tool Outputs):\n{summary_obj.summary}\n")

            # Log and keep artifacts in state for downstream tools/UI
            logger.info(
                "Execute summary for thread_id=%s, step_idx=%s:\n%s\n--- end summary ---\nArtifacts: %s",
                thread_id, state.get("step_idx", 0), summary_obj.summary, summary_obj.artifacts
            )

            # Remove verbose ToolMessages before adding the assistant summary
            all_messages = [m for m in all_messages if not isinstance(m, ToolMessage)]
            all_messages.append(AIMessage(content=summary_obj.summary))

            # Optionally expose artifacts to the graph state for later nodes/UI
            for summary_art in summary_obj.artifacts:
                if summary_art.uri and summary_art.uri not in [a.get("uri") for a in state.get("artifacts", [])]:
                    state["artifacts"].append(summary_art.dict())

            # Completion gate: look for TASK_COMPLETE token at start or anywhere in the summary
            done = "USER_OBJECTIVE_COMPLETE" in summary_obj.summary

            if done:
                return {
                    "messages": all_messages,
                    "artifacts": state.get("artifacts", []),
                    "done": True
                }


        # Prepend system for policy
        prompt = [
            {"role": "system", "content": EXECUTE_SYSTEM},
            {"role": "user", "content": f"CEL.md (context):\n{cel_snip}"},
            {"role": "user", "content": f"Artifacts:\n{state.get('artifacts', [])}"},
        ]
        
        # logger.info(f"Execute node for thread_id={thread_id}, step_idx={state.get('step_idx',0)} generating response with prompt:\n{prompt}\n--- end prompt ---\n\n")
        
        resp = await _model_with_tools.ainvoke(prompt)
        
        logger.info(f"Execute node for thread_id={thread_id}, step_idx={state.get('step_idx',0)} got response:\n{resp}\n--- end response ---\n\n")
        
        all_messages.append(resp)

        return {
            "messages": all_messages,
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

def route_after_clarify(state: MCPState) -> Literal["todo", "reply"]:
    return "reply" if state.get("need_clarification") and state.get("clarifying_question") else "todo"

async def route_after_execute(state: MCPState, config: RunnableConfig) -> Literal["tools", "reply"]:
    try:
        if state.get("done"):
            return "reply"
        
        messages = state["messages"]
        
        # logger.info(f"Route after execute checking messages for thread_id={config['configurable']['thread_id']}, step_idx={state.get('step_idx',0)}:\n{messages}\n--- end messages ---\n\n")
        
        last_message = messages[-1]
        
        if isinstance(last_message, AIMessage):
            if last_message.tool_calls: 
                return "tools"
            
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
    _builder.add_node("execute", execute_node)
    _builder.add_node("tools", ToolNode(tools=_tools))
    _builder.add_node("reply", reply_node)

    _builder.add_edge(START, "clarify")
    _builder.add_conditional_edges("clarify", route_after_clarify, {"todo": "todo", "reply": "reply"})
    _builder.add_edge("todo", "execute")
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
            need_clarification=False,
            clarifying_question=None,
            artifacts=[],
        )
        
        while True:
            raw = await ws.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"event": "error", "detail": "Malformed JSON"})
                continue

            if payload.get("type") != "user_message":
                await ws.send_json({"event": "error", "detail": "send {type:'user_message', text: ...}"})
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

            config = {
                "configurable": {
                    "thread_id": tid,
                    "emit": emitter,
                    "exec_ctx": {"bucket": DEFAULT_BUCKET, "base_prefix": base_prefix},
                }
            }
            
            state["messages"].append(HumanMessage(content=user_text + files_note))
            
            result = await graph.ainvoke(state, config=config)

            logger.info(f"WS MCP graph thread_id={tid} node returned updates: {result}")

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.exception("WebSocket error: %s", e)
        try:
            await ws.send_json({"event": "error", "detail": str(e)})
        finally:
            await ws.close()