# core/lite_llm_model.py
import os
from dotenv import load_dotenv
from openai import OpenAI
from openai import BadRequestError

load_dotenv()

# ===== toggle =====
# USE_LITELLM=1 -> talk to your LiteLLM proxy
# USE_LITELLM=0 -> talk to OpenAI directly
USE_LITELLM = os.getenv("USE_LITELLM", "1") == "1"

if USE_LITELLM:
    BASE_URL = os.environ["LITELLM_PROXY_URL"].rstrip("/")
    API_KEY  = os.environ["LITELLM_PROXY_API_KEY"]
    RAW_MODEL = os.getenv("LITELLM_MODEL_ID", "azure/gpt-5-chat-eastus2")
    # Some users prefix "litellm_proxy/..."; strip if present
    MODEL = RAW_MODEL.split("litellm_proxy/")[-1]
else:
    # OpenAI direct (defaults to global API; override if you use US/EU regional endpoints)
    BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    API_KEY  = os.environ["OPENAI_API_KEY"]
    MODEL    = os.getenv("OPENAI_MODEL_ID", "gpt-4o-mini")

# One official OpenAI client works for both paths (LiteLLM is OpenAI-compatible)
client = OpenAI(base_url=BASE_URL, api_key=API_KEY)

def chat(messages, tools=None, tool_choice="auto", temperature=0.3, stream=False, max_tokens=None):
    """
    OpenAI Chat Completions call via either:
      - LiteLLM proxy (if USE_LITELLM=1), or
      - OpenAI direct (if USE_LITELLM=0).
    Supports function tools when backend supports them.
    """
    kwargs = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "stream": stream,
    }
    if tools:
        kwargs["tools"] = tools
    if tool_choice:
        kwargs["tool_choice"] = tool_choice
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens

    try:
        return client.chat.completions.create(**kwargs)
    except BadRequestError as e:
        # If the backend rejects tool params (common on some Bedrock routes),
        # retry once without tool-use so non-tool models still work gracefully.
        msg = str(e)
        if ("UnsupportedParamsError" in msg or "drop_params" in msg) and (tools or tool_choice):
            kwargs.pop("tools", None)
            kwargs.pop("tool_choice", None)
            return client.chat.completions.create(**kwargs)
        raise

# Expose which side we're using + the resolved model for any callers that care
BACKEND = "litellm" if USE_LITELLM else "openai"
ACTIVE_MODEL = MODEL
