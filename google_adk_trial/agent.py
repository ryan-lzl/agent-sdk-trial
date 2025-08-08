import os
from dotenv import load_dotenv

import litellm
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

# Ensure .env is loaded when running via `adk run`
load_dotenv()

# --- Force all requests through LiteLLM Proxy (OpenAI-compatible) ---
# (so provider auto-detection like 'azure/' won't matter)
litellm.use_litellm_proxy = True  # requires litellm >= 1.72.x

# Also set OpenAI-compatible envs so any downstream client sees them
os.environ.setdefault("OPENAI_API_BASE", os.getenv("LITELLM_PROXY_API_BASE", ""))
os.environ.setdefault("OPENAI_API_KEY", os.getenv("LITELLM_PROXY_API_KEY", ""))

# Read the model id from env and prefix with 'litellm_proxy/' to bypass provider heuristics
model_id = os.getenv("LITELLM_MODEL_ID", "azure/gpt-5-chat-eastus2")
if not model_id.startswith("litellm_proxy/"):
    model_id = f"litellm_proxy/{model_id}"

root_agent = LlmAgent(
    model=LiteLlm(
        model=model_id,
        # Pass base+key explicitly so background threads / inner calls have them
        api_base=os.getenv("LITELLM_PROXY_API_BASE", ""),
        api_key=os.getenv("LITELLM_PROXY_API_KEY", ""),
        # Double safety: force OpenAI-compatible transport for the proxy
        custom_llm_provider="openai",
    ),
    name="Google_LiteLLM_Agent",
    instruction="You are a helpful assistant. Keep answers concise unless asked otherwise.",
)
