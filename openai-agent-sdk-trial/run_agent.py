import asyncio
import os
import openai
from dotenv import load_dotenv

from agents import Agent, Runner, set_default_openai_client, set_tracing_disabled
from agents import OpenAIChatCompletionsModel  # avoids provider-prefix parsing

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

async def main():
    agent = Agent(
        name="ProxyAgent",
        instructions="You are a helpful assistant.",
        # Use model object so 'azure/...', 'gemini-...' etc. work without 'prefix' issues
        model=OpenAIChatCompletionsModel(model=MODEL_ID, openai_client=client),
    )

    print(f"--- Running agent with model '{MODEL_ID}' via proxy at {PROXY_URL} ---")
    result = await Runner().run(agent, "Say which model you are and greet me briefly.")
    print(result.final_output or result.error)

if __name__ == "__main__":
    asyncio.run(main())
