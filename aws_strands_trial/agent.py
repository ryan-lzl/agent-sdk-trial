# agent.py
import os
import sys
from dotenv import load_dotenv

# --- Strands SDK ---
from strands import Agent, tool
from strands.models.litellm import LiteLLMModel
from strands.handlers.callback_handler import PrintingCallbackHandler  # streams tokens
from strands_tools import calculator, current_time

# --- LiteLLM (force proxy routing) ---
import litellm

# --- NEW (for Web Fetch & Summarize) ---
import requests
from bs4 import BeautifulSoup

load_dotenv()

# Route ALL traffic through your LiteLLM proxy
litellm.use_litellm_proxy = True

# Make proxy visible to OpenAI-compatible clients
os.environ.setdefault("OPENAI_API_BASE", os.getenv("LITELLM_PROXY_API_BASE", ""))
os.environ.setdefault("OPENAI_API_KEY", os.getenv("LITELLM_PROXY_API_KEY", ""))

raw_model_id = os.getenv("LITELLM_MODEL_ID", "azure/gpt-5-chat-eastus2")
MODEL_ID = raw_model_id if raw_model_id.startswith("litellm_proxy/") else f"litellm_proxy/{raw_model_id}"

SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    # Tip: keep identity consistent if users ask "what model are you?"
    # e.g., 'If asked, say you are "GPT-5 Thinking".'
    "You are a helpful assistant. Prefer concise answers unless asked otherwise."
)

@tool
def shout(text: str) -> str:
    """Return the text in uppercase (demo tool)."""
    return text.upper()

# --- NEW TOOL: Web Fetch & Summarize ---
@tool
def http_fetch_and_clean(url: str, timeout_sec: int = 10, max_chars: int = 6000) -> str:
    """
    Fetch a web page and return cleaned text (trimmed). Use with a follow-up
    LLM prompt like 'summarize the fetched content' or 'extract steps'.
    """
    headers = {"User-Agent": "strands-agent/1.0 (+lite-llm-proxy)"}
    r = requests.get(url, headers=headers, timeout=timeout_sec)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # Remove scripts/styles/nav-like chrome
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
        tag.extract()

    text = " ".join(soup.get_text(separator=" ").split())
    if len(text) > max_chars:
        text = text[:max_chars] + " ...[truncated]"
    return text

class CleanPrintingHandler(PrintingCallbackHandler):
    """
    Adds a neat prefix before streaming starts and *always* emits a newline
    after the final token (or tool output). This prevents the next 'you >'
    prompt from sticking to the last character of the assistant message.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._opened = False

    def on_message_start(self, *args, **kwargs):
        if not self._opened:
            # Prefix once per assistant message
            print("assistant > ", end="", flush=True)
            self._opened = True
        return super().on_message_start(*args, **kwargs)

    def on_message_end(self, *args, **kwargs):
        out = super().on_message_end(*args, **kwargs)
        # Ensure final newline
        if self._opened:
            print("", flush=True)
            self._opened = False
        return out

    # Some tool executions may be the last emitted event; ensure newline too
    def on_tool_end(self, *args, **kwargs):
        out = super().on_tool_end(*args, **kwargs)
        if self._opened:
            print("", flush=True)
            self._opened = False
        return out

def create_agent() -> Agent:
    model = LiteLLMModel(
        model_id=MODEL_ID,
        params={"temperature": 0.3},
        client_args={
            "api_key": os.getenv("LITELLM_PROXY_API_KEY", ""),
            "api_base": os.getenv("LITELLM_PROXY_API_BASE", ""),
        },
    )
    return Agent(
        model=model,
        tools=[calculator, current_time, shout, http_fetch_and_clean],  # <-- added tool
        system_prompt=SYSTEM_PROMPT,
        callback_handler=CleanPrintingHandler(),  # clean streaming UX
    )

def repl() -> None:
    agent = create_agent()
    print(f"\nStrands REPL ready (model: {MODEL_ID})")
    print("Type your message. Commands: /reset  /exit\n")

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
            agent = create_agent()
            print("↺ session reset.")
            continue

        # Invoke agent: the handler streams output. Do NOT print the result.
        _ = agent(user)

        # Hard-stop safeguard to ensure newline even on timing races.
        sys.stdout.write("\n")
        sys.stdout.flush()

if __name__ == "__main__":
    # Recommended: python -u agent.py (unbuffered) for snappier streaming
    repl()
