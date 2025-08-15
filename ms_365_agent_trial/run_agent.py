#!/usr/bin/env python3
import os
import json
import asyncio
from typing import List, Dict, Any

from dotenv import load_dotenv
import openai
import requests
from bs4 import BeautifulSoup

# ---------- Env / Client ----------
load_dotenv()

PROXY_URL = os.environ["LITELLM_PROXY_URL"]           # e.g., https://litellm-stg.aip.gov.sg
PROXY_KEY = os.environ["LITELLM_PROXY_API_KEY"]       # e.g., sk-...
RAW_MODEL = os.getenv("LITELLM_MODEL_ID", "azure/gpt-5-chat-eastus2")

# If someone pasted a litellm_proxy/ prefix (useful for the litellm *library*),
# strip it here because we're calling an OpenAI-compatible endpoint directly.
MODEL = RAW_MODEL.split("litellm_proxy/")[-1]

client = openai.OpenAI(base_url=PROXY_URL, api_key=PROXY_KEY)

# ---------- Tool: fetch_and_summarize ----------
def fetch_and_summarize(url: str, timeout_sec: int = 10, max_chars: int = 6000) -> str:
    """Fetch a web page, strip scripts/styles/nav/etc., return cleaned text (trimmed)."""
    headers = {"User-Agent": "ms365-agent-sample/1.0 (+lite-llm-proxy)"}
    r = requests.get(url, headers=headers, timeout=timeout_sec)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
        tag.extract()

    text = " ".join(soup.get_text(separator=" ").split())
    return text[:max_chars] + (" ...[truncated]" if len(text) > max_chars else "")

TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "fetch_and_summarize",
            "description": "Fetch a web page and return cleaned plain text for summarization.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "HTTP/HTTPS URL to fetch"},
                    "timeout_sec": {"type": "integer", "minimum": 1, "maximum": 60, "default": 10},
                    "max_chars": {"type": "integer", "minimum": 1000, "maximum": 40000, "default": 6000}
                },
                "required": ["url"],
                "additionalProperties": False,
            },
        },
    }
]

# ---------- Simple chat loop with tool calling ----------
SYSTEM = (
    "You are a helpful, concise assistant. "
    "Use tools when they help answer accurately. If you use fetch_and_summarize, cite key points succinctly."
)

def call_tools(tool_calls: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Execute model-requested tools and return tool role messages."""
    tool_messages: List[Dict[str, str]] = []
    for call in tool_calls:
        fn = call.function
        name = fn.name
        try:
            args = json.loads(fn.arguments or "{}")
        except json.JSONDecodeError:
            args = {}

        if name == "fetch_and_summarize":
            print(f"\n[tool] start: {name} input={args}", flush=True)
            try:
                out = fetch_and_summarize(
                    url=args.get("url", ""),
                    timeout_sec=int(args.get("timeout_sec", 10)),
                    max_chars=int(args.get("max_chars", 6000)),
                )
                preview = (out[:160] + "…") if len(out) > 160 else out
                print(f"[tool] end: {len(out)} chars | preview='{preview}'\n", flush=True)
            except Exception as e:
                out = f"ERROR: {type(e).__name__}: {e}"
                print(f"[tool] error: {out}\n", flush=True)
            tool_messages.append(
                {"role": "tool", "tool_call_id": call.id, "name": name, "content": out}
            )
        else:
            tool_messages.append(
                {"role": "tool", "tool_call_id": call.id, "name": name, "content": "ERROR: unknown tool"}
            )
    return tool_messages

def print_streamed_content(stream):
    """Stream assistant tokens to stdout."""
    for chunk in stream:
        delta = chunk.choices[0].delta
        if delta and getattr(delta, "content", None):
            print(delta.content, end="", flush=True)

def _tool_calls_payload(tool_calls) -> list:
    """
    Convert SDK tool_calls objects into plain dicts acceptable by Chat Completions.
    Avoids deprecated .dict() and pydantic v2 warnings.
    """
    payload = []
    for tc in (tool_calls or []):
        func = getattr(tc, "function", None)
        payload.append({
            "id": tc.id,
            "type": tc.type,
            "function": {
                "name": getattr(func, "name", None),
                "arguments": getattr(func, "arguments", None),
            }
        })
    return payload

async def main():
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM}
    ]

    print(f"Microsoft 365 Agent (custom engine) – interactive mode\n"
          f"Model: {MODEL}\nProxy: {PROXY_URL}\n"
          f"Commands: /reset  /exit\n")

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
            messages = [{"role": "system", "content": SYSTEM}]
            print("↺ session reset.")
            continue

        messages.append({"role": "user", "content": user})

        # Step 1: non-streamed call to see if a tool is requested
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.3,
        )

        choice = resp.choices[0]
        msg = choice.message

        # If the model asked to call a tool, execute tool(s), then do a streamed follow-up
        if msg.tool_calls:
            tool_msgs = call_tools(msg.tool_calls)

            # Append the assistant 'tool call' stub + tool outputs back to history
            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": _tool_calls_payload(msg.tool_calls),  # <-- no deprecated .dict()
            })
            messages.extend(tool_msgs)

            # Step 2: streamed final with tools present (Bedrock/LiteLLM requires tools=)
            print("assistant > ", end="", flush=True)
            stream = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOLS,               # <-- IMPORTANT: include tools again
                tool_choice="auto",        # safe default; you can switch to "none" to force no more tool calls
                stream=True,
                temperature=0.2,
            )
            print_streamed_content(stream)
            print()

            # Optional: capture the exact final text for history with a quick non-streamed call
            final = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOLS,           # <-- include tools here too
                tool_choice="auto",
                temperature=0.2,
            )
            messages.append({"role": "assistant", "content": final.choices[0].message.content or ""})

        else:
            # No tools — print assistant reply
            print(f"assistant > {msg.content}\n")
            messages.append({"role": "assistant", "content": msg.content or ""})

if __name__ == "__main__":
    asyncio.run(main())
