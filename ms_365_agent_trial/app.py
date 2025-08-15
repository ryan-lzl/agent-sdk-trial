# app.py
import os
import json
import uuid
import traceback
from typing import List, Dict, Any

from dotenv import load_dotenv
from aiohttp import web

from microsoft.agents.core.models.activity import Activity

from core.lite_llm_model import chat
from tools.fetch_and_summarize import TOOL_SPEC, run as run_fetch

load_dotenv()

SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "You are a helpful, concise assistant. Use tools when they help."
)

TOOLS: List[Dict[str, Any]] = [TOOL_SPEC]

# ---- enforce a healthy first fetch so models don't ask for a second round
FETCH_MIN_CHARS = int(os.getenv("FETCH_MIN_CHARS", "8000"))  # can override in .env

# --- Simple in-memory sessions for multi-turn ---
SESSIONS: Dict[str, List[Dict[str, Any]]] = {}  # sid -> list[{"role": ..., "content": ...}]
COOKIE_NAME = "sid"


def _ensure_sid(request: web.Request) -> str:
    sid = request.cookies.get(COOKIE_NAME)
    if not sid:
        sid = uuid.uuid4().hex[:12]
    if sid not in SESSIONS:
        SESSIONS[sid] = []
    return sid


def _append_history(sid: str, role: str, content: str) -> None:
    SESSIONS[sid].append({"role": role, "content": content})


def _build_messages(sid: str, new_user_text: str) -> List[Dict[str, Any]]:
    msgs: List[Dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    msgs.extend(SESSIONS[sid])  # prior turns
    msgs.append({"role": "user", "content": new_user_text})
    return msgs


def _tool_call_messages(msg) -> List[Dict[str, Any]]:
    """Convert tool_calls into assistant stub + tool outputs (ONE ROUND ONLY)."""
    addl: List[Dict[str, Any]] = []
    addl.append({
        "role": "assistant",
        "content": msg.content or "",
        "tool_calls": [
            {
                "id": tc.id,
                "type": tc.type,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                }
            } for tc in (msg.tool_calls or [])
        ],
    })

    for tc in (msg.tool_calls or []):
        try:
            args = json.loads(tc.function.arguments or "{}")
        except json.JSONDecodeError:
            args = {}

        if tc.function.name == "fetch_and_summarize":
            # enforce a generous first fetch to avoid second-round retries
            timeout = int(args.get("timeout_sec", 12))
            max_chars = int(args.get("max_chars", 6000))
            if max_chars < FETCH_MIN_CHARS:
                max_chars = FETCH_MIN_CHARS

            out = run_fetch(
                url=args.get("url", ""),
                timeout_sec=timeout,
                max_chars=max_chars,
            )
            addl.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": "fetch_and_summarize",
                "content": out,
            })
        else:
            addl.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": tc.function.name,
                "content": "ERROR: unknown tool",
            })
    return addl


# -------------------------
# SSE helpers (emit BYTES)
# -------------------------
def _sse_event(event: str, data: Dict[str, Any]) -> bytes:
    frame = f"event: {event}\n" + "data: " + json.dumps(data, ensure_ascii=False) + "\n\n"
    return frame.encode("utf-8")


async def _stream_reply(resp: web.StreamResponse, text: str | None = None) -> None:
    await resp.write(_sse_event("done", {"text": text or ""}))


# -------------------------
# ONE-ROUND tools, then stream the final answer
# -------------------------
async def handle_engine_turn_streaming(resp: web.StreamResponse, messages: List[Dict[str, Any]]) -> str:
    """
    Probe once (non-stream).
    If tool_calls exist -> execute them ONCE, emit tool events.
    Then do a single streaming call for the answer.
    """
    # Probe for tools once
    probe = chat(messages, tools=TOOLS, tool_choice="auto", stream=False)
    msg = probe.choices[0].message

    if getattr(msg, "tool_calls", None):
        # Append assistant stub + tool results (one round only)
        messages.extend(_tool_call_messages(msg))

        # Emit tool events so they appear BEFORE the final answer
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            # reflect enforced min chars in the visible args (so it's clear we fetched enough)
            shown_args = dict(args)
            if shown_args.get("max_chars", 0) and shown_args["max_chars"] < FETCH_MIN_CHARS:
                shown_args["max_chars"] = FETCH_MIN_CHARS

            await resp.write(_sse_event("tool", {
                "phase": "start",
                "name": tc.function.name,
                "args": shown_args
            }))
            out_msg = next((m for m in messages if m.get("role") == "tool" and m.get("tool_call_id") == tc.id), None)
            if out_msg:
                preview = out_msg["content"][:200] + ("…" if len(out_msg["content"]) > 200 else "")
                await resp.write(_sse_event("tool", {
                    "phase": "end",
                    "name": tc.function.name,
                    "chars": len(out_msg["content"]),
                    "preview": preview
                }))

    # Final streaming answer (single call)
    stream = chat(messages, tools=TOOLS, tool_choice="auto", stream=True)
    final_text_parts: List[str] = []
    for chunk in stream:
        delta = getattr(chunk.choices[0].delta, "content", None)
        if delta:
            delta_text = delta if isinstance(delta, str) else str(delta)
            final_text_parts.append(delta_text)
            await resp.write(_sse_event("token", {"delta": delta_text}))
    final_text = "".join(final_text_parts)
    return final_text


# -------------------------
# aiohttp app (unchanged except for using the function above)
# -------------------------
async def make_app() -> web.Application:
    app = web.Application()

    async def home(request: web.Request) -> web.Response:
        sid = _ensure_sid(request)
        html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>M365 Agent Playground (local)</title>
  <style>
    :root {{
      --bg:#f8fafc; --panel:#ffffff; --accent:#2563eb; --muted:#6b7280; --fg:#111827;
      --assistant:#f3f4f6; --user:#dbeafe; --tool:#fef3c7; --border:#e5e7eb;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; background:var(--bg); color:var(--fg); font: 14px/1.4 system-ui, -apple-system, Segoe UI, Roboto, Arial; }}
    header {{ padding:16px 20px; background:var(--panel); border-bottom:1px solid var(--border); display:flex; align-items:center; gap:12px; position:sticky; top:0; z-index:1; }}
    header .dot {{ width:10px; height:10px; border-radius:50%; background:var(--accent); }}
    header h1 {{ font-size:16px; margin:0; }}
    #wrap {{ max-width:1200px; margin: 0 auto; padding: 20px; }}
    #log {{ background:#ffffff; border:1px solid var(--border); border-radius:12px; padding:16px; height: 68vh; overflow:auto; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }}
    .msg {{ max-width: 88%; margin: 8px 0; padding: 10px 12px; border-radius: 12px; white-space: pre-wrap; word-wrap: break-word; }}
    .assistant {{ background: var(--assistant); border: 1px solid var(--border); }}
    .user {{ background: var(--user); border: 1px solid #bfdbfe; align-self: flex-end; margin-left: auto; }}
    .tool {{ background: var(--tool); border: 1px dashed #f59e0b; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
    .row {{ display: flex; flex-direction: column; }}
    #bar {{ display:flex; gap:8px; margin-top:12px; }}
    #t {{ flex:1; padding: 12px; border-radius: 10px; border:1px solid var(--border); background:#ffffff; color:var(--fg); }}
    #send, #reset {{ padding: 12px 16px; border-radius: 10px; border:0; background:var(--accent); color:white; cursor:pointer; }}
    #reset {{ background:#6b7280; }}
    .muted {{ color: var(--muted); font-size: 12px; margin-top: 6px; }}
  </style>
</head>
<body>
<header><div class="dot"></div><h1>M365 Agent Playground (local)</h1></header>
<div id="wrap">
  <div id="log" class="row"></div>
  <div id="bar">
    <input id="t" placeholder="Type a message and press Enter…"/>
    <button id="send">Send</button>
    <button id="reset">Reset</button>
  </div>
  <div class="muted">Model and tools run on your local server. Tool calls appear before the answer.</div>
</div>
<script>
const log = document.getElementById('log');
const t   = document.getElementById('t');
const sendBtn = document.getElementById('send');
const resetBtn = document.getElementById('reset');

function bubble(cls, text="") {{
  const div = document.createElement('div');
  div.className = 'msg ' + cls;
  div.textContent = text;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
  return div;
}}

async function streamChat(text) {{
  bubble('user', text);
  t.value = "";

  let a = null;

  const res = await fetch('/chat', {{
    method:'POST',
    headers: {{ 'Content-Type':'application/json' }},
    body: JSON.stringify({{ text }})
  }});

  if (!res.ok || !res.body) {{
    bubble('assistant', "[error] HTTP " + res.status);
    return;
  }}

  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";

  while (true) {{
    const {{ value, done }} = await reader.read();
    if (done) break;
    buf += dec.decode(value, {{ stream:true }});
    const parts = buf.split("\\n\\n");
    buf = parts.pop();
    for (const frame of parts) {{
      const lines = frame.split("\\n");
      let event = null, data = null;
      for (const ln of lines) {{
        if (ln.startsWith("event:")) event = ln.slice(6).trim();
        else if (ln.startsWith("data:")) data = ln.slice(5).trim();
      }}
      if (!event) continue;
      try {{ if (data) data = JSON.parse(data); }} catch {{ data = {{}}; }}

      if (event === "tool") {{
        const phase = data.phase || "";
        if (phase === "start") {{
          bubble('tool', "[tool start] " + (data.name || "") + "  args=" + JSON.stringify(data.args || {{}}));
        }} else if (phase === "end") {{
          bubble('tool', "[tool end] " + (data.name || "") + "  " + (data.chars||0) + " chars\\n" + (data.preview || ""));
        }}
      }} else if (event === "token") {{
        if (!a) a = bubble('assistant', "");
        a.textContent += (data.delta || "");
        log.scrollTop = log.scrollHeight;
      }} else if (event === "error") {{
        if (!a) a = bubble('assistant', "");
        a.textContent = "[error] " + (data.detail || data.error || "unknown");
      }} else if (event === "done") {{
        // end of stream
      }}
    }}
  }}
}}

function go() {{
  const text = t.value.trim();
  if (!text) return;
  streamChat(text);
}}

sendBtn.onclick = go;
t.addEventListener('keydown', (e) => {{
  if (e.key === 'Enter' && !e.shiftKey) {{ e.preventDefault(); go(); }}
}});
resetBtn.onclick = async () => {{
  await fetch('/reset', {{ method:'POST' }});
  log.innerHTML = "";
}};
</script>
</body></html>"""
        resp = web.Response(text=html, content_type="text/html")
        resp.set_cookie("sid", sid, path="/")
        return resp

    async def health(_req: web.Request) -> web.Response:
        return web.json_response({"ok": True})

    async def reset(request: web.Request) -> web.Response:
        sid = _ensure_sid(request)
        SESSIONS[sid] = []
        return web.json_response({"ok": True})

    async def chat_stream(request: web.Request) -> web.StreamResponse:
        sid = _ensure_sid(request)
        try:
            payload = await request.json()
            text = (payload.get("text") or "").strip()
            resp = web.StreamResponse(status=200, headers={
                "Content-Type": "text/event-stream; charset=utf-8",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            })
            await resp.prepare(request)

            if not text:
                await resp.write(_sse_event("error", {"error": "missing 'text' in body"}))
                await _stream_reply(resp, "")
                return resp

            messages = _build_messages(sid, text)
            final_text = await handle_engine_turn_streaming(resp, messages)

            _append_history(sid, "user", text)
            _append_history(sid, "assistant", final_text)

            await _stream_reply(resp, final_text)
            return resp

        except Exception as e:
            resp = web.StreamResponse(status=200, headers={"Content-Type": "text/event-stream; charset=utf-8"})
            await resp.prepare(request)
            await resp.write(_sse_event("error", {"error": "internal_error", "detail": str(e)}))
            traceback.print_exc()
            await _stream_reply(resp, "")
            return resp

    async def messages_http(request: web.Request) -> web.Response:
        sid = _ensure_sid(request)
        try:
            payload = await request.json()
            activity = Activity.model_validate(payload)
            text = (activity.text or "").strip()
            if not text:
                return web.json_response({"error": "activity missing 'text'"}, status=400)

            messages = _build_messages(sid, text)
            probe = chat(messages, tools=TOOLS, tool_choice="auto", stream=False)
            msg = probe.choices[0].message
            if getattr(msg, "tool_calls", None):
                messages.extend(_tool_call_messages(msg))
                final = chat(messages, tools=TOOLS, tool_choice="auto", stream=False)
                reply = final.choices[0].message.content or ""
            else:
                reply = msg.content or ""

            _append_history(sid, "user", text)
            _append_history(sid, "assistant", reply)
            return web.json_response({"reply": reply})

        except Exception as e:
            traceback.print_exc()
            return web.json_response({"error": "internal_error", "detail": str(e)}, status=500)

    app.router.add_get("/", home)
    app.router.add_get("/healthz", health)
    app.router.add_post("/reset", reset)
    app.router.add_post("/chat", chat_stream)
    app.router.add_post("/api/messages", messages_http)
    return app


if __name__ == "__main__":
    port = int(os.getenv("PORT", "3978"))
    web.run_app(make_app(), host="127.0.0.1", port=port)
