# agent.py — Google ADK + LiteLLM + Web Fetch tool
# CHANGE: added lightweight prints around the tool to show when it's used.
import os
from dotenv import load_dotenv

import litellm
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

# --- Web Fetch & Summarize tool deps ---
import requests
from bs4 import BeautifulSoup

# Ensure .env is loaded when running via `adk run` or the wrapper
load_dotenv()

# --- Force all requests through LiteLLM Proxy (OpenAI-compatible) ---
litellm.use_litellm_proxy = True  # requires litellm >= 1.72.x

# Also set OpenAI-compatible envs so any downstream client sees them
os.environ.setdefault("OPENAI_API_BASE", os.getenv("LITELLM_PROXY_API_BASE", ""))
os.environ.setdefault("OPENAI_API_KEY", os.getenv("LITELLM_PROXY_API_KEY", ""))

# Read the model id from env and prefix with 'litellm_proxy/' to bypass provider heuristics
model_id = os.getenv("LITELLM_MODEL_ID", "azure/gpt-5-chat-eastus2")
if not model_id.startswith("litellm_proxy/"):
    model_id = f"litellm_proxy/{model_id}"

# Web Fetch & Clean tool
def http_fetch_and_clean(url: str, timeout_sec: int = 10, max_chars: int = 6000) -> str:
    """
    Fetch a web page and return cleaned plain text (trimmed).
    Use with prompts like: "fetch and summarize <url>".
    """
    # --- BEGIN: small, explicit tool-use logs ---
    print(f"[tool] http_fetch_and_clean: start url={url}", flush=True)
    try:
        headers = {"User-Agent": "adk-agent/1.0 (+lite-llm-proxy)"}
        r = requests.get(url, headers=headers, timeout=timeout_sec)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")
        # Remove scripts/styles/nav chrome
        for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
            tag.extract()

        text = " ".join(soup.get_text(separator=" ").split())
        if len(text) > max_chars:
            text = text[:max_chars] + " ...[truncated]"

        print(f"[tool] http_fetch_and_clean: success chars={len(text)}", flush=True)
        return text
    except Exception as e:
        print(f"[tool] http_fetch_and_clean: ERROR {type(e).__name__}: {e}", flush=True)
        raise
    # --- END: small, explicit tool-use logs ---


root_agent = LlmAgent(
    model=LiteLlm(
        model=model_id,
        api_base=os.getenv("LITELLM_PROXY_API_BASE", ""),
        api_key=os.getenv("LITELLM_PROXY_API_KEY", ""),
        custom_llm_provider="openai",
    ),
    name="Google_LiteLLM_Agent",
    instruction="You are a helpful assistant. Keep answers concise unless asked otherwise.",
    tools=[http_fetch_and_clean],  # unchanged list; tool now logs when used
)
