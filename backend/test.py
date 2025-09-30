# app/agents/ws_mcp.py (enhanced)

from __future__ import annotations
import os, uuid, json, base64, asyncio
from typing import Any, Dict, Optional, List, Callable, Literal

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.chat_models import init_chat_model
from langgraph.graph import StateGraph, START, END

from app.aws.s3_client import S3Client
from app.core.logging import get_logger

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

model = init_chat_model("openai:gpt-4.1-mini")

_mcp_client: Optional[MultiServerMCPClient] = None
_model_with_tools = None
_tools_ready = asyncio.Lock()


async def _ensure_tools():
    global _mcp_client, _model_with_tools
    async with _tools_ready:
        if _mcp_client is not None and _model_with_tools is not None:
            return
        _mcp_client = MultiServerMCPClient(
            {
                "sandbox": {
                    "url": SANDBOX_MCP_WS,
                    "transport": "streamable_http",
                },
            }
        )
        tools = await _mcp_client.get_tools()
        _model_with_tools = model.bind_tools(tools)
        logger.info("MCP tools bound over WebSocket.")


# -----------------------
# 2) CEL helpers (S3)
# -----------------------

def _cel_key(base_prefix: str) -> str:
    return f"{base_prefix}/CEL.md"


def _read_cel(base_prefix: str) -> str:
    key = _cel_key(base_prefix)
    try:
        obj = s3c.get_object(key)
        return obj["Body"].decode("utf-8") if isinstance(obj["Body"], (bytes, bytearray)) else obj["Body"]
    except Exception:
        return ""


def _append_cel(base_prefix: str, section: str, content: str) -> None:
    prev = _read_cel(base_prefix)
    new = prev + f"\n\n## {section}\n\n{content.strip()}\n"
    s3c.put_bytes(key=_cel_key(base_prefix), data=new.encode("utf-8"), content_type="text/markdown")


# -----------------------
# 3) System prompts
# -----------------------
CLARIFY_SYSTEM = (
    "You are a careful PM. Decide if the user's request needs clarification to proceed.\n"
    "If clarification is needed, ask ONE concise question. If not, answer exactly 'NO_CLARIFICATION_NEEDED'."
)

TODO_SYSTEM = (
    "You are a project planner. Convert the user's task into a short, actionable TODO list.\n"
    "Keep it concise and focused on concrete steps the tools can execute.\n"
    "Return a Markdown checklist with 3-7 items. Avoid fluffy text."
)


def exec_system(bucket: str, base_prefix: str) -> str:
    return (
        "You can use tools. For the sandbox, only use S3 URIs under "
        f"'s3://{bucket}/{base_prefix}/uploads/'.\n"
        "Prefer the high-level tool 'sandbox.run_step' if available (it will fetch inputs, run, and upload outputs).\n"
        "If you produce an artifact, write it to "
        f"'s3://{bucket}/{base_prefix}/artifacts/'.\n"
        "When you call the sandbox tool, include a succinct 'code' field for what will be run, and request stdout capture."
    )


# -----------------------
# 4) State type & emit helper
# -----------------------
class MCPState(dict):
    """Conversation + execution state passed through the graph."""
    messages: List[dict]
    _exec_ctx: Dict[str, str]            # {bucket, base_prefix}
    _emit: Callable[[dict], Any]         # WS event emitter
    step_idx: int
    max_steps: int
    done: bool
    need_clarification: bool
    clarifying_question: Optional[str]
    artifacts: List[dict]


# -----------------------
# 5) Graph nodes
# -----------------------
async def clarify_node(state: MCPState):
    emit = state["_emit"]
    emit({"event": "node", "name": "clarify"})

    bucket = state["_exec_ctx"]["bucket"]
    base_prefix = state["_exec_ctx"]["base_prefix"]

    cel_snip = _read_cel(base_prefix)
    user_plus = [
        {"role": "system", "content": CLARIFY_SYSTEM},
        {"role": "system", "content": f"CEL.md (context):\n{cel_snip}"},
        *state["messages"],
    ]
    resp = await model.ainvoke(user_plus)
    out = (resp.content or "").strip()
    need = out.upper() != "NO_CLARIFICATION_NEEDED"

    if need:
        state["need_clarification"] = True
        state["clarifying_question"] = out
        _append_cel(base_prefix, "assistant.clarify", out)
        emit({"event": "clarify", "question": out})
        # The WS loop will pause and wait for user's answer, then update state accordingly
        return {"need_clarification": True}

    state["need_clarification"] = False
    return {"messages": [{"role": "assistant", "content": "No clarification needed. Proceeding."}]}


def route_after_clarify(state: MCPState) -> Literal["todo", "reply"]:
    # If we still need clarification, we will handle it in WS loop and re-enter graph after user reply.
    return "reply" if state.get("need_clarification") else "todo"


async def todo_node(state: MCPState):
    emit = state["_emit"]
    emit({"event": "node", "name": "write_todos"})

    resp = await model.ainvoke([{"role": "system", "content": TODO_SYSTEM}, *state["messages"]])
    todo_md = resp.content or "- [ ] Step 1\n- [ ] Step 2"

    base_prefix = state["_exec_ctx"]["base_prefix"]
    _append_cel(base_prefix, "plan.todo", todo_md)

    return {
        "messages": [{"role": "assistant", "content": f"Here’s the plan:\n\n{todo_md}\n\nI’ll start executing the steps."}],
        "todo": todo_md,
    }


def _has_tool_calls(msg: Any) -> bool:
    return bool(getattr(msg, "tool_calls", None) or (isinstance(msg, dict) and msg.get("tool_calls")))


def route_after_execute(state: MCPState) -> Literal["tools", "reply"]:
    last = state["messages"][-1]
    # If the model emitted tool calls, run tools next; otherwise we can proceed to reply
    return "tools" if _has_tool_calls(last) else "reply"


async def execute_node(state: MCPState):
    emit = state["_emit"]
    emit({"event": "node", "name": "execute", "step": state.get("step_idx", 0)})

    bucket = state["_exec_ctx"]["bucket"]
    base_prefix = state["_exec_ctx"]["base_prefix"]
    sys = exec_system(bucket, base_prefix)

    # Prepend system for policy
    prompt = [{"role": "system", "content": sys}, *state["messages"]]
    resp = await _model_with_tools.ainvoke(prompt)

    # Keep rolling message history
    state["messages"].append(resp)

    # Do not mark done here; tools (next node) will actually execute and emit code/stdout
    return {"messages": state["messages"]}


async def tools_node(state: MCPState):
    """
    Execute pending tool calls from the last assistant message.
    We expect the sandbox MCP tool to return a JSON-serializable result that may include:
      {
        "code": "...",                # the executed code cell
        "stdout": "...",              # captured stdout
        "artifacts": [
           {"name": "report.md", "uri": "s3://...", "content_type": "text/markdown", "size": 12345}
        ],
        "done": true|false
      }
    We'll surface code/stdout/artifacts via WS events and append to CEL.md.
    """
    emit = state["_emit"]
    emit({"event": "node", "name": "tools"})

    last = state["messages"][-1]
    tool_calls = last.get("tool_calls") if isinstance(last, dict) else getattr(last, "tool_calls", [])

    if not tool_calls:
        return {}

    bucket = state["_exec_ctx"]["bucket"]
    base_prefix = state["_exec_ctx"]["base_prefix"]

    # Execute each tool call sequentially
    any_done = False
    step_idx = state.get("step_idx", 0)

    for call in tool_calls:
        name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
        args = call.get("args") if isinstance(call, dict) else getattr(call, "args", {})

        # Execute via MCP client
        result = await _mcp_client.call_tool(name=name, arguments=args)

        # Try to coerce result into dict
        try:
            payload = result if isinstance(result, dict) else json.loads(result)
        except Exception:
            payload = {"raw": result}

        code = payload.get("code")
        stdout = payload.get("stdout") or ""
        artifacts = payload.get("artifacts") or []
        done_flag = bool(payload.get("done", False))

        # UI surfacing
        if code:
            emit({"event": "code", "code": code, "filename": f"step_{step_idx}.py"})
        if stdout:
            emit({"event": "sandbox.stdout", "text": stdout})

        # CEL logging
        cel_block = []
        if code:
            cel_block.append(f"```python\n{code}\n```")
        if stdout:
            cel_block.append(f"**stdout**\n\n```\n{stdout}\n```")
        if artifacts:
            manifest = "\n".join([f"- {a.get('name','artifact')} → {a.get('uri','')}" for a in artifacts])
            cel_block.append(f"**artifacts**\n\n{manifest}")
        if cel_block:
            _append_cel(base_prefix, f"exec.step_{step_idx}", "\n\n".join(cel_block))

        # Accumulate artifacts
        state.setdefault("artifacts", []).extend(artifacts)

        any_done = any_done or done_flag

    # Increment step and possibly mark done
    state["step_idx"] = step_idx + 1

    if any_done or state["step_idx"] >= state.get("max_steps", 20):
        state["done"] = True

    # After running tools, add a short assistant acknowledgement so the model can continue reasoning
    state["messages"].append({"role": "assistant", "content": "Executed tool(s) and recorded outputs."})

    return {
        "messages": state["messages"],
        "artifacts": state.get("artifacts", []),
        "done": state.get("done", False),
        "step_idx": state["step_idx"],
    }


async def reply_node(state: MCPState):
    emit = state["_emit"]
    emit({"event": "node", "name": "respond"})

    # If we’re here because clarification was needed but not yet received, just prompt the user
    if state.get("need_clarification") and state.get("clarifying_question"):
        msg = {"event": "clarify", "question": state["clarifying_question"]}
        emit(msg)
        return {"messages": [{"role": "assistant", "content": state["clarifying_question"]}]}

    # Emit final answer + artifacts
    artifacts = state.get("artifacts", [])
    answer_text = (
        "Done. Executed steps via the sandbox and recorded outputs in CEL.md."
        if state.get("done") else
        "Partial progress recorded. You can provide more details or ask me to continue."
    )

    emit({"event": "answer", "text": answer_text})
    if artifacts:
        emit({"event": "answer.artifacts", "items": artifacts})

    # Also include a plain assistant message for clients expecting chat-only
    return {"messages": [{"role": "assistant", "content": answer_text}]}


# -----------------------
# 6) Build graph once
# -----------------------
_builder = StateGraph(MCPState)
_builder.add_node("clarify", clarify_node)
_builder.add_node("todo", todo_node)
_builder.add_node("execute", execute_node)
_builder.add_node("tools", tools_node)
_builder.add_node("reply", reply_node)

_builder.add_edge(START, "clarify")
_builder.add_conditional_edges("clarify", route_after_clarify, {"todo": "todo", "reply": "reply"})
_builder.add_edge("todo", "execute")
_builder.add_conditional_edges("execute", route_after_execute, {"tools": "tools", "reply": "reply"})
_builder.add_edge("tools", "execute")
_builder.add_edge("reply", END)

graph = _builder.compile()


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
        b64 = f.get("b64")
        if not b64:
            continue
        data = base64.b64decode(b64)
        key = f"{base_prefix}/uploads/{name}"
        man = s3c.put_bytes(key=key, data=data, content_type=ctype).to_dict()
        out.append({"name": name, "uri": man["uri"], "content_type": ctype, "size": str(man["size"])})
    return out


# -----------------------
# 8) WebSocket endpoint with event protocol + clarify handshake
# -----------------------
@router.websocket("/ws/mcp_graph")
async def ws_mcp_graph(
    ws: WebSocket,
    run_id: Optional[str] = Query(default=None),
):
    """
    Client → Server JSON per turn:
      {
        "type": "user_message",
        "text": "...",
        "files": [{"name":"file.csv","content_type":"text/csv","b64":"..."}] // optional
      }

    Server → Client events during a run:
      {"event":"node", "name": "clarify|write_todos|execute|tools|respond"}
      {"event":"clarify", "question": "..."}
      {"event":"code", "code":"...", "filename":"step_0.py"}
      {"event":"sandbox.stdout", "text":"..."}
      {"event":"answer", "text":"..."}
      {"event":"answer.artifacts", "items": [ {name, uri, ...}, ... ]}
      {"event":"error", "detail": "..."}
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
        rid = run_id or uuid.uuid4().hex
        base_prefix = f"runs/{rid}"
        exec_ctx = {"bucket": DEFAULT_BUCKET, "base_prefix": base_prefix}

        # Conversation state for this socket
        state: MCPState = MCPState(
            messages=[],
            _exec_ctx=exec_ctx,
            _emit=emitter,
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
            files = payload.get("files") or []

            # Optional uploads → S3
            uploaded = await _upload_ws_files(files, DEFAULT_BUCKET, base_prefix)
            files_note = ""
            if uploaded:
                bullet = "\n".join([f"- {u['name']}: {u['uri']}" for u in uploaded])
                files_note = f"\n\nUploaded files (S3 URIs):\n{bullet}"

            # Append user message to rolling context
            state["messages"].append({"role": "user", "content": user_text + files_note})

            # ---- Graph phase 1: clarify
            result = await graph.ainvoke(state)
            # Merge deltas
            state.update(result)

            # If clarification required, pause turn and wait for reply
            if state.get("need_clarification") and state.get("clarifying_question"):
                # Wait for a follow-up message on the same socket
                follow = await ws.receive_json()
                if follow.get("type") == "user_message":
                    clar_text = (follow.get("text") or "").strip()
                    _append_cel(base_prefix, "user.clarification", clar_text)
                    # Add as additional context and clear the need flag to continue
                    state["messages"].append({"role": "user", "content": f"Clarification: {clar_text}"})
                    state["need_clarification"] = False
                    state["clarifying_question"] = None
                else:
                    await ws.send_json({"event": "error", "detail": "Expected user_message for clarification."})

            # ---- Graph phase 2: plan → execute loop
            # Re-enter starting from TODO now that clarification is resolved
            # (Run small manual loop: todo → (execute → tools)* → reply)
            todo_res = await todo_node(state)
            state.update(todo_res)

            while not state.get("done") and state.get("step_idx", 0) < state.get("max_steps", 20):
                exec_res = await execute_node(state)
                state.update(exec_res)

                # If model didn’t call tools, break to reply
                if (lambda m: not _has_tool_calls(m[-1]))(state["messages"]):
                    break

                tool_res = await tools_node(state)
                state.update(tool_res)

                if state.get("done"):
                    break

            # ---- Final respond
            reply_res = await reply_node(state)
            state.update(reply_res)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.exception("WebSocket error: %s", e)
        try:
            await ws.send_json({"event": "error", "detail": str(e)})
        finally:
            await ws.close()