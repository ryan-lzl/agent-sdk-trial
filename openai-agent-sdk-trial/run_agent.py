import asyncio
import os
import openai
from dotenv import load_dotenv

from agents import (
    Agent,
    Runner,
    SQLiteSession,
    set_default_openai_client,
    set_tracing_disabled,
    OpenAIChatCompletionsModel,   # avoids provider-prefix parsing
    function_tool,
)

# Stream token deltas
from openai.types.responses import ResponseTextDeltaEvent

# Web fetch tool deps
import requests
from bs4 import BeautifulSoup

load_dotenv()

PROXY_URL = os.environ["LITELLM_PROXY_URL"]
PROXY_KEY = os.environ["LITELLM_PROXY_API_KEY"]

# Map ACTIVE_MODEL alias -> actual model id from .env
ACTIVE = os.getenv("OPENAI_AGENT_SDK_ACTIVE_MODEL", "GPT4O_MINI").upper()
alias_env_key = f"OPENAI_AGENT_SDK_MODEL_ALIAS_{ACTIVE}"
MODEL_ID = os.getenv(alias_env_key)
if not MODEL_ID:
    raise ValueError(
        f"ACTIVE_MODEL='{ACTIVE}' not found. "
        f"Set {alias_env_key} in .env or change OPENAI_AGENT_SDK_ACTIVE_MODEL."
    )

# OpenAI client pointed at your LiteLLM proxy (no /v1 at the end)
client = openai.AsyncOpenAI(base_url=PROXY_URL, api_key=PROXY_KEY)
set_default_openai_client(client)

# Disable tracing to OpenAI (prevents stray 401s with proxy keys)
set_tracing_disabled(True)

# ------------------------------------------------------------------
# fetch_and_summarize tool (same behavior as your other stacks)
# ------------------------------------------------------------------
@function_tool(name_override="fetch_and_summarize")
def fetch_and_summarize(url: str, timeout_sec: int = 10, max_chars: int = 6000) -> str:
    """
    Fetch a web page, strip HTML (scripts/styles/nav/headers/footers), and return cleaned text.
    Args:
        url: The URL to fetch.
        timeout_sec: HTTP timeout in seconds.
        max_chars: Truncate cleaned text to this length (for token safety).
    """
    headers = {"User-Agent": "openai-agents-demo/1.0 (+lite-llm-proxy)"}
    r = requests.get(url, headers=headers, timeout=timeout_sec)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
        tag.extract()

    text = " ".join(soup.get_text(separator=" ").split())
    if len(text) > max_chars:
        text = text[:max_chars] + " ...[truncated]"
    return text


async def chat_loop():
    """Interactive REPL with streaming + tool-use logs, preserving context via SQLiteSession."""
    agent = Agent(
        name="ProxyAgent",
        instructions="You are a helpful assistant.",
        model=OpenAIChatCompletionsModel(model=MODEL_ID, openai_client=client),
        tools=[fetch_and_summarize],
    )

    # Keep conversation history automatically across turns
    session_id = os.getenv("OPENAI_AGENT_SDK_SESSION_ID", "cli_session")
    session = SQLiteSession(session_id)  # in-memory DB unless you pass a file path

    print(f"--- Interactive mode (model '{MODEL_ID}', proxy {PROXY_URL}) ---")
    print("Type your message. Commands: /reset  /exit\n")

    while True:
        # read input without blocking the event loop
        user = await asyncio.to_thread(input, "you > ")
        msg = user.strip()
        if not msg:
            continue
        if msg in {"/exit", "/quit"}:
            print("bye!")
            return
        if msg in {"/reset", "/r"}:
            await session.clear_session()
            print("↺ session reset.")
            continue

        # Start a streamed run
        print("assistant > ", end="", flush=True)
        result = Runner.run_streamed(
            agent,
            input=msg,          # user message
            session=session,    # keep the thread context
        )

        # Stream both token deltas and tool events
        async for event in result.stream_events():
            # token-by-token streaming
            if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                print(event.data.delta, end="", flush=True)
                continue

            # higher-level run events: show tool start/end
            if event.type == "run_item_stream_event":
                item = event.item
                if item.type == "tool_call_item":
                    # Tool being called
                    tool_name = getattr(item, "name", None) or getattr(item, "tool_name", None) or "tool"
                    print(f"\n[tool] start: {tool_name}", flush=True)
                elif item.type == "tool_call_output_item":
                    # Tool finished
                    out_preview = str(getattr(item, "output", ""))[:160]
                    print(f"\n[tool] end: {len(str(getattr(item, 'output', '')))} chars | preview='{out_preview}'", flush=True)

        # newline after the streamed message finishes
        print()


async def main():
    await chat_loop()


if __name__ == "__main__":
    asyncio.run(main())
