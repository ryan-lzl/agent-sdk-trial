# core/lite_llm_model.py
import os
from dotenv import load_dotenv
import openai

load_dotenv()

PROXY_URL = os.environ["LITELLM_PROXY_URL"].rstrip("/")
PROXY_KEY = os.environ["LITELLM_PROXY_API_KEY"]
RAW_MODEL = os.getenv("LITELLM_MODEL_ID", "azure/gpt-5-chat-eastus2")

# The Agents SDK app talks to *your* engine. Our engine is a thin layer that
# uses an OpenAI-compatible client pointed at LiteLLM.
client = openai.OpenAI(base_url=PROXY_URL, api_key=PROXY_KEY)

# Some users prefix "litellm_proxy/..." when using the litellm python lib;
# here we call the OpenAI-compatible endpoint directly, so strip that if present.
MODEL = RAW_MODEL.split("litellm_proxy/")[-1]

def chat(messages, tools=None, tool_choice="auto", temperature=0.3, stream=False):
    """
    OpenAI Chat Completions call via LiteLLM proxy. Supports function tools.
    """
    return client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=tools or None,
        tool_choice=tool_choice,
        temperature=temperature,
        stream=stream,
    )
