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
  3) execute    -> Accomplish the steps in the TODO list:
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
from starlette.concurrency import run_in_threadpool

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from langgraph.graph import StateGraph, END

from app.services.openai_client import OpenAIClient
from app.models.orchestration.state import WSState

from app.core.logging import get_logger

from app.nodes.responder import respond
from app.nodes.planner import write_todos
from app.nodes.execute import execute
from app.nodes.clarification import check_clarification

from app.utils.files.file_storing import save_ws_files, save_b64_files
from app.utils.files.file_paths import run_dir, public_base_path
from app.utils.files.cel import read_cel, append_cel

router = APIRouter()

oai = OpenAIClient()

logger = get_logger(__name__)

# ----------------------------- Build Graph ------------------------------------

def build_graph():
    g = StateGraph(WSState)
    g.add_node("check_clarification", check_clarification)  # may set simple_qa/need_clarification/clarify_question
    g.add_node("write_todos", write_todos)
    g.add_node("execute", execute)                          # must set need_clarification=True + clarify_question when stuck
    g.add_node("respond", respond)

    g.set_entry_point("check_clarification")

    # After initial check: go direct to respond for simple Q&A; otherwise plan work.
    def _route_after_check(state: WSState) -> Literal["respond", "write_todos"]:
        if not state.get("need_clarification") and state.get("simple_qa", False):
            return "respond"
        return "write_todos"

    g.add_conditional_edges(
        "check_clarification",
        _route_after_check,
        {"respond": "respond", "write_todos": "write_todos"},
    )

    # Plan -> Execute
    g.add_edge("write_todos", "execute")

    # Decide to keep executing, clarify, or finish
    def _loop_or_respond(state: WSState) -> Literal["execute", "respond", "clarify"]:
        if state.get("done"):
            return "respond"
        if state.get("need_clarification"):
            # prevent infinite clarify loops
            if state.get("clarify_attempts", 0) >= state.get("max_clarify", 2):
                # fall back to a partial respond with explicit ask embedded
                return "respond"
            return "clarify"
        if state.get("step_idx", 0) >= state.get("max_steps", 7):
            return "respond"
        return "execute"

    g.add_conditional_edges(
        "execute",
        _loop_or_respond,
        {"execute": "execute", "respond": "respond", "clarify": "check_clarification"},
    )

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
            state = await run_in_threadpool(check_clarification, state)

            if state.get("need_clarification"):
                await websocket.send_json({"event": "clarify", "question": state.get("clarifying_question", "")})
                clarify_msg = await websocket.receive_json()
                if clarify_msg.get("type") == "user_message":
                    append_cel(run_id, "user.clarification", clarify_msg.get("text", "").strip())
                    state["text"] = state["text"] + "\n\nClarification: " + clarify_msg.get("text", "").strip()

            # --- write_todos ---
            await websocket.send_json({"event": "node", "name": "write_todos"})
            state = await run_in_threadpool(write_todos, state)

            # --- execute loop ---
            while True:
                await websocket.send_json({"event": "node", "name": "execute", "step": state.get("step_idx", 0)})

                state = await run_in_threadpool(execute, state)

                # Make sure execute() sets a dict:
                # state["code"] = {"code": code_str, "filename": f"step_{state['step_idx']}.py"}
                code_payload = state.get("code") or {}
                await websocket.send_json({"event": "code", **code_payload})

                await websocket.send_json({"event": "sandbox.stdout", "text": state.get("stdout", "")})

                if state.get("done"):
                    break

            # --- respond ---
            await websocket.send_json({"event": "node", "name": "respond"})
            state = await run_in_threadpool(respond, state)
            await websocket.send_json({"event": "answer", "text": state.get("answer", "")})
            await websocket.send_json({"event": "answer.artifacts", "items": state.get("answer_artifacts", [])})
    except WebSocketDisconnect:
        return
    except Exception as e:
        await websocket.send_json({"event": "error", "detail": str(e)})
        await websocket.close()
