# repl.py
import os
import json
from typing import List, Dict, Any

from dotenv import load_dotenv
from core.lite_llm_model import chat
from tools.fetch_and_summarize import TOOL_SPEC, run as run_fetch

load_dotenv()

SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "You are a helpful, concise assistant. Use tools when they help.",
)

TOOLS: List[Dict[str, Any]] = [TOOL_SPEC]


def main():
    print("Microsoft 365 Agent (SDK-backed engine) – interactive mode")
    print("Commands: /exit  /reset\n")
    while True:
        try:
            user = input("you > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye!")
            break

        if not user:
            continue
        if user in {"/exit", "/quit"}:
            print("bye!")
            break
        if user in {"/reset", "/r"}:
            print("↺ (stateless sample) nothing to reset.\n")
            continue

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ]

        # 1) Probe for tool usage
        resp = chat(messages, tools=TOOLS, tool_choice="auto", stream=False)
        choice = resp.choices[0]
        msg = choice.message

        if msg.tool_calls:
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
                if tc.function.name == "fetch_and_summarize":
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    print(f"[tool] fetch_and_summarize start: {args}")
                    out = run_fetch(
                        url=args.get("url", ""),
                        timeout_sec=int(args.get("timeout_sec", 10)),
                        max_chars=int(args.get("max_chars", 6000)),
                    )
                    print(f"[tool] fetch_and_summarize end: {len(out)} chars\n")
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

            final = chat(messages, tools=TOOLS, tool_choice="auto", stream=False)
            print(f"assistant > {final.choices[0].message.content or ''}\n")
        else:
            print(f"assistant > {msg.content or ''}\n")


if __name__ == "__main__":
    main()
