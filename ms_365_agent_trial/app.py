# app.py
import os
import json
from typing import List, Dict, Any

from dotenv import load_dotenv

# ---- Microsoft 365 Agents SDK (Python) ----
# Install these from TestPyPI before running (see README).
from microsoft_agents_core import AgentMessage, AgentApplication, TurnContext
from microsoft_agents_hosting_aiohttp import create_web_app, start_web_server

# ---- Your engine and tool
from core.lite_llm_model import chat
from tools.fetch_and_summarize import TOOL_SPEC, run as run_fetch

load_dotenv()

SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "You are a helpful, concise assistant. Use tools when they help.",
)

TOOLS: List[Dict[str, Any]] = [TOOL_SPEC]


class SimpleAgent(AgentApplication):
    """
    Minimal Agent wired into the M365 Agents SDK pipeline.
    - Receives messages from channels (Playground/Teams later).
    - For each user message, calls your LiteLLM-backed engine.
    - Executes tool calls (`fetch_and_summarize`) when requested.
    """

    async def on_message(self, turn_context: TurnContext) -> None:
        user_text = (turn_context.activity.text or "").strip()
        if not user_text:
            await turn_context.send_activity("I didn't get any text.")
            return

        # Build classic OpenAI chat messages (system+user); you can add memory later.
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ]

        # 1) Non-streamed probe to see if tool is requested
        resp = chat(messages, tools=TOOLS, tool_choice="auto", stream=False)
        choice = resp.choices[0]
        msg = choice.message

        # If there are tool calls, execute them and do a final turn
        if msg.tool_calls:
            # Append assistant stub + tool results back to messages
            messages.append({
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
                    } for tc in msg.tool_calls
                ],
            })

            for tc in msg.tool_calls:
                # Only our single tool in this sample
                if tc.function.name == "fetch_and_summarize":
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    out = run_fetch(
                        url=args.get("url", ""),
                        timeout_sec=int(args.get("timeout_sec", 10)),
                        max_chars=int(args.get("max_chars", 6000)),
                    )
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": "fetch_and_summarize",
                        "content": out,
                    })
                else:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.function.name,
                        "content": "ERROR: unknown tool",
                    })

            # 2) Final answer with tool results in context
            final = chat(messages, tools=TOOLS, tool_choice="auto", stream=False)
            text = final.choices[0].message.content or "(no content)"
            await turn_context.send_activity(text)
        else:
            # No tools: reply directly
            text = msg.content or "(no content)"
            await turn_context.send_activity(text)


if __name__ == "__main__":
    # Host the Agent with aiohttp via the Agents SDK
    app = create_web_app(SimpleAgent())
    port = int(os.getenv("PORT", "3978"))
    print(f"Microsoft 365 Agents SDK host listening on http://localhost:{port}")
    start_web_server(app, port=port)
