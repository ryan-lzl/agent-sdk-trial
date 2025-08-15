import os
import uuid
from dotenv import load_dotenv

load_dotenv()

from langchain_litellm import ChatLiteLLM
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import HumanMessage

# --- NEW: tool decorator + deps for Web Fetch & Summarize ---
from langchain_core.tools import tool
import requests
from bs4 import BeautifulSoup

# --- NEW: callback to log tool usage ---
from langchain.callbacks.base import BaseCallbackHandler

class ToolLogHandler(BaseCallbackHandler):
    """Log when tools start/end/error so you can see tool usage in the console."""

    def on_tool_start(self, serialized=None, input_str=None, **kwargs):
        # serialized is usually a dict like {"name": "<tool_name>", ...}
        name = None
        if isinstance(serialized, dict):
            name = serialized.get("name") or serialized.get("id")
        elif isinstance(serialized, str):
            name = serialized
        # print on a new line so it doesn't glue to streaming tokens
        print(f"\n[tool] start: {name} input={input_str}", flush=True)

    def on_tool_end(self, output, **kwargs):
        out_preview = str(output)
        if len(out_preview) > 140:
            out_preview = out_preview[:140] + "…"
        print(f"\n[tool] end: output_len={len(str(output))} preview={out_preview!r}", flush=True)

    def on_tool_error(self, error, **kwargs):
        print(f"\n[tool] error: {type(error).__name__}: {error}", flush=True)

# --- LiteLLM Proxy envs ---
api_base = os.getenv("LITELLM_PROXY_API_BASE", "")
api_key = os.getenv("LITELLM_PROXY_API_KEY", "")
model_id = os.getenv("LITELLM_MODEL_ID", "azure/gpt-5-chat-eastus2")

# Force routing via LiteLLM proxy
if not model_id.startswith("litellm_proxy/"):
    model_id = f"litellm_proxy/{model_id}"

# --- LLM with streaming enabled ---
llm = ChatLiteLLM(
    model=model_id,
    api_base=api_base,
    api_key=api_key,
    streaming=True,  # stream tokens to stdout via callback
)

# --- Web Fetch & Summarize tool (same behavior as before) ---
@tool("fetch_and_summarize")
def fetch_and_summarize(url: str, timeout_sec: int = 10, max_chars: int = 6000) -> str:
    """Fetch a web page, strip HTML (scripts/styles/nav), and return cleaned text (trimmed)."""
    headers = {"User-Agent": "langgraph-agent/1.0 (+lite-llm-proxy)"}
    r = requests.get(url, headers=headers, timeout=timeout_sec)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
        tag.extract()

    text = " ".join(soup.get_text(separator=" ").split())
    if len(text) > max_chars:
        text = text[:max_chars] + " ...[truncated]"
    return text

# --- LangGraph agent with in-memory checkpointer ---
checkpoint = InMemorySaver()
agent = create_react_agent(
    llm,
    tools=[fetch_and_summarize],  # register the tool
    prompt="You are a helpful, concise assistant.",
    checkpointer=checkpoint,
)

# One session/thread id for this CLI run (required by checkpointer)
session_id = os.getenv("SESSION_ID", str(uuid.uuid4())[:8])

print("LangGraph chatbot is running. Type your questions (or 'exit' to quit).")
print(f"[session thread_id: {session_id}]")

while True:
    try:
        user_input = input("User: ")
    except (EOFError, KeyboardInterrupt):
        print()  # clean newline on Ctrl-D/C
        break

    if user_input.strip().lower() in {"exit", "quit"}:
        break

    # Build message list
    messages = [HumanMessage(content=user_input)]

    # Streaming tokens to stdout via callback; do NOT reprint final text
    cfg = {
        "configurable": {"thread_id": session_id},
        # --- NEW: add ToolLogHandler alongside the token stream handler ---
        "callbacks": [StreamingStdOutCallbackHandler(), ToolLogHandler()],
    }

    # Label once, then stream; no second print of the same answer
    print("Assistant: ", end="", flush=True)
    agent.invoke({"messages": messages}, config=cfg)
    print()  # newline after streaming
