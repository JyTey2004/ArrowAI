# app/api/routes/ws.py
"""
WebSocket assistant (end-to-end) using LangGraph with a single tool: the Code Sandbox.

Flow per user turn:
- Client sends a JSON message with {text, files?}. Files should already be uploaded
  (e.g., via your /tmp endpoints) into tmp/<run_id>/, or sent inline as base64 and
  saved server-side before the graph run.
- Graph nodes:
  1) check_clarification -> LLM may ask for more info/if it's just a simple question we can just go to step 4
  2) write_todos         -> LLM breaks down the task into deliverables and write a TODO list in CEL.md
  3) plan_and_execute    -> Accomplish the steps in the TODO list:
        3.0  -> LLM reads CEL.md and plans next step
        3.1  -> LLM generates one Python cell/Other tools could be added here in future
        3.2  -> Cell is executed in the sandbox, results collected and appended to CEL.md
        3.3  -> Loop 3.0-3.2 until done or max steps reached
  4) respond             -> LLM summarizes the result for the user

This keeps exactly ONE tool in the loop: the sandbox. The LLM never calls other tools.

Client protocol (WebSocket):
- Connect to:  ws://<host>/ws/assist?run_id=<id>
- Send JSON payloads
"""
from __future__ import annotations

import os
from typing import Literal

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from langgraph.graph import StateGraph, END

from app.services.openai_client import OpenAIClient
from app.tools.sandbox import sandbox, code_llm, eval_llm
from app.tools.sandbox.executor import ExecRequest
from app.models.orchestration.state import WSState

from app.core.logging import get_logger

from app.services.agent.responder import respond

from app.utils.files.file_storing import save_ws_files, save_b64_files
from app.utils.files.file_paths import cel_path, run_dir, public_base_path
from app.utils.files.cel import read_cel, append_cel

router = APIRouter()

oai = OpenAIClient()

logger = get_logger(__name__)

# ------------------------------- Prompts --------------------------------------
WRITER_SYSTEM = (
    "You are a senior Python data engineer. Output ONLY raw Python code for one cell.\n"
    "Environment: cwd is the run directory. Use relative paths (e.g., 'spend.csv').\n"
    "Read CEL.md (provided) to understand available files and next steps.\n"
)

CLARIFY_SYSTEM = (
    "You are a careful PM. Decide if the user's request needs clarification to proceed with execution.\n"
    "If clarification is needed, ask ONE concise question. If not, answer 'NO_CLARIFICATION_NEEDED'.\n"
)

TODOS_SYSTEM = (
    "You are a delivery lead. Break the task into a concise TODO list (markdown) of concrete, executable steps and deliverables.\n"
    "Each step should be a small, manageable action, with clear inputs and outputs. That can be done within a single cell of code.\n"
    "Generate markdown only (no fences, no commentary)."
)

# ------------------------------- Graph Nodes ----------------------------------

def check_clarification(state: WSState) -> WSState:
    run_id, text = state["run_id"], state["text"].strip()
    cel_snip = read_cel(run_id)
    file_info = state.get("files", []) or []
    prompt = f"CEL.md (context):\n{cel_snip}\n\nUser task:\n{text}\n\nArtifacts uploaded:\n{file_info}\n\nDo we need clarification?"
    resp = oai.generate(model="gpt-4.1-mini", system=CLARIFY_SYSTEM, text=prompt, max_output_tokens=200, temperature=0)
    out = oai.output_text(resp).strip()
    need = out.upper() != "NO_CLARIFICATION_NEEDED"
    state["need_clarification"] = need
    if need:
        state["clarifying_question"] = out
    return state


def write_todos(state: WSState) -> WSState:
    run_id = state["run_id"]
    cel_snip = read_cel(run_id)
    prompt = (
        "Write a TODO list for implementing the user's task.\n\n" +
        f"CEL.md (context):\n{cel_snip}\n\nUser task:\n{state['text']}\n"
    )
    resp = oai.generate(model="gpt-4.1-mini", system=TODOS_SYSTEM, text=prompt, max_output_tokens=500, temperature=0.2)
    todos = oai.output_text(resp).strip()
    state["todos_md"] = todos
    append_cel(run_id, "plan.todos", todos)
    return state


def plan_and_execute(state: WSState) -> WSState:
    run_id = state["run_id"]
    step_idx = int(state.get("step_idx", 0))
    max_steps = int(state.get("max_steps", 20))

    # 3.0 LLM plans next step based on CEL
    cel_snip = read_cel(run_id)
    plan_prompt = (
        "From CEL.md and TODOs, decide the NEXT concrete step to execute now.\n"
        "Return a 1-3 bullet micro-plan. Then produce ONE Python cell to execute that plan.\n"
        "Rules: output ONLY code for the cell (no fences, no commentary). Use cwd-relative paths.\n\n"
        f"CEL.md (context):\n{cel_snip}\n\n"
        f"User task:\n{state['text']}\n"
    )
    resp = oai.generate(model="gpt-4.1-mini", system=WRITER_SYSTEM, text=plan_prompt,
                        files=[str(cel_path(run_id))], max_output_tokens=1200, temperature=0.1)
    code = oai.output_text(resp).strip()
    # strip fences if present
    if "```" in code:
        import re
        m = re.search(r"```(?:python|py)?\s*\n(.*?)\n```", code, re.DOTALL|re.IGNORECASE)
        code = (m.group(1) if m else code.replace("```python", "").replace("```", "")).strip()

    state["code"] = code

    # 3.2 Execute in sandbox
    req = ExecRequest(code=code, timeout_s=120, task=state["text"], use_llm_writer=False)
    res = sandbox.exec_cell(run_id, req, code_llm=code_llm, eval_llm=eval_llm)

    state["stdout"], state["stderr"], state["artifacts"] = res.stdout, res.stderr, res.files_out

    # loop control
    step_idx += 1
    state["step_idx"] = step_idx
    # Heuristic: stop if stderr empty and code produced at least one artifact change or step_idx hit max
    done = (step_idx >= max_steps) or (not res.stderr and len(res.files_out) > 0)
    state["done"] = done
    return state

# ----------------------------- Build Graph ------------------------------------

def build_graph():
    g = StateGraph(WSState)
    g.add_node("check_clarification", check_clarification)
    g.add_node("write_todos", write_todos)
    g.add_node("plan_and_execute", plan_and_execute)
    g.add_node("respond", respond)

    g.set_entry_point("check_clarification")

    # conditional from clarification to next step
    def _route_after_check(state: WSState) -> Literal["respond", "write_todos"]:
        # If no clarification is needed AND the task seems like a simple Q&A (no files in TODOs), jump to respond
        if not state.get("need_clarification"):
            return "write_todos"  # still write TODOs for consistency; change to "respond" if you want instant QA
        return "write_todos"

    g.add_conditional_edges("check_clarification", _route_after_check, {"respond": "respond", "write_todos": "write_todos"})

    # plan_and_execute can loop to itself until done
    g.add_edge("write_todos", "plan_and_execute")

    def _loop_or_respond(state: WSState) -> Literal["plan_and_execute", "respond"]:
        return "respond" if state.get("done") else "plan_and_execute"

    g.add_conditional_edges("plan_and_execute", _loop_or_respond, {"plan_and_execute": "plan_and_execute", "respond": "respond"})

    g.add_edge("respond", END)
    return g.compile()

GRAPH = build_graph()

# ------------------------------ WebSocket -------------------------------------

@router.websocket("/ws/assist")
async def ws_assist(websocket: WebSocket, run_id: str = Query(...)):
    await websocket.accept()
    base = public_base_path(websocket)
    try:
        while True:
            msg = await websocket.receive_json()
            if not isinstance(msg, dict):
                await websocket.send_json({"event": "error", "detail": "Expected JSON object"})
                continue
            if msg.get("type") != "user_message":
                await websocket.send_json({"event": "error", "detail": "send {'type':'user_message','text':...}"})
                continue

            text = (msg.get("text") or "").strip()
            files = msg.get("files", []) or []

            file_info = []

            for file in files:
                file_info.append({"name": file["name"], "size": file.get("size", 0), "content_type": file.get("content_type", "application/octet-stream")})

            # optional: inline base64 files
            # inline file saving (supports your 'files' shape)
            ws_files = msg.get("files") or []
            if isinstance(ws_files, list) and ws_files and isinstance(ws_files[0], dict) and "content" in ws_files[0]:
                save_ws_files(run_dir(run_id), ws_files)
            # still support files_b64 if client uses it
            inline_files = msg.get("files_b64", []) or []
            if inline_files:
                save_b64_files(run_dir(run_id), inline_files)

            state: WSState = {"run_id": run_id, "text": text, "files": file_info, "step_idx": 0, "max_steps": 20, "done": False, "base": base}

            logger.info(f"Starting WS assist for run_id={run_id}")

            # stream the graph
            await websocket.send_json({"event": "node", "name": "check_clarification"})
            state = check_clarification(state)
            logger.info(f"check_clarification done, need_clarification={state.get('need_clarification')}")
            if state.get("need_clarification"):
                await websocket.send_json({"event": "clarify", "question": state.get("clarifying_question", "")})
                # wait for one reply
                clarify_msg = await websocket.receive_json()
                if clarify_msg.get("type") == "user_message":
                    # append clarification to CEL
                    append_cel(run_id, "user.clarification", clarify_msg.get("text", "").strip())
                    # merge text
                    state["text"] = state["text"] + "\n\nClarification: " + clarify_msg.get("text", "").strip()

            await websocket.send_json({"event": "node", "name": "write_todos"})
            state = write_todos(state)
            await websocket.send_json({"event": "todos", "markdown": state.get("todos_md", "")})
            
            logger.info(f"write_todos done, todos_md={state.get('todos_md', '')}")
            
            logger.info(f"Starting plan_and_execute loop for run_id={run_id}")

            # loop plan & execute
            while True:
                await websocket.send_json({"event": "node", "name": "plan_and_execute", "step": state.get("step_idx", 0)})
                state = plan_and_execute(state)
                await websocket.send_json({"event": "code", "text": state.get("code", "")})
                await websocket.send_json({"event": "sandbox.stdout", "text": state.get("stdout", "")})
                # if state.get("stderr"):
                #     await websocket.send_json({"event": "sandbox.stderr", "text": state.get("stderr", "")})
                # await websocket.send_json({"event": "sandbox.artifacts", "items": state.get("artifacts", [])})
                if state.get("done"):
                    break

            await websocket.send_json({"event": "node", "name": "respond"})
            state = respond(state)
            await websocket.send_json({"event": "answer", "text": state.get("answer", "")})
    except WebSocketDisconnect:
        return
    except Exception as e:
        await websocket.send_json({"event": "error", "detail": str(e)})
        await websocket.close()
