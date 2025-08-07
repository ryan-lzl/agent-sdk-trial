# run_agent.py (Replacement Version)

import asyncio
import os
import openai
from dotenv import load_dotenv
from agents import Agent, Runner, set_default_openai_client

# --- START: CONFIGURATION FROM ENVIRONMENT ---

load_dotenv()

LITELLM_PROXY_URL = os.getenv("LITELLM_PROXY_URL")
PROXY_API_KEY = os.getenv("LITELLM_PROXY_API_KEY")
# Use the new environment variable name
MODEL_ALIAS_SONNET = os.getenv("OPENAI_AGENT_SDK_MODEL_ALIAS_SONNET")
MODEL_ALIAS_GPT4O = os.getenv("OPENAI_AGENT_SDK_MODEL_ALIAS_GPT4O")

if not all([LITELLM_PROXY_URL, PROXY_API_KEY, MODEL_ALIAS_SONNET, MODEL_ALIAS_GPT4O]):
    raise ValueError("One or more required environment variables are missing. "
                     "Please check LITELLM_PROXY_URL, LITELLM_PROXY_API_KEY, "
                     "and OPENAI_AGENT_SDK_MODEL_ALIAS_SONNET, OPENAI_AGENT_SDK_MODEL_ALIAS_GPT4O in the .env file.")

# Create and set the default client that the agent will use
custom_client = openai.AsyncOpenAI(
    base_url=LITELLM_PROXY_URL,
    api_key=PROXY_API_KEY,
)
set_default_openai_client(custom_client)

# --- END: CONFIGURATION FROM ENVIRONMENT ---


async def main():
    """
    This function creates an agent for the Anthropic Sonnet model and sends
    the request to the LiteLLM Proxy configured via the custom client.
    """

    # Agent initialization uses the model string with the "litellm/" prefix
    sonnet_agent = Agent(
        name="Anthropic_Sonnet_Agent",
        instructions="You are a helpful and friendly assistant from Anthropic. Your name is Claude.",
        model=MODEL_ALIAS_GPT4O
    )
    
    runner = Runner()

    print(f"--- Running agent with model '{MODEL_ALIAS_GPT4O}' via proxy at {LITELLM_PROXY_URL} ---")
    
    sonnet_result = await runner.run(sonnet_agent, "Explain the concept of 'Constitutional AI' in a few sentences.")
    
    if sonnet_result.final_output:
        print(sonnet_result.final_output)
    else:
        print("The Sonnet agent did not produce a final output.")
        if sonnet_result.error:
            print(f"Error: {sonnet_result.error}")


if __name__ == "__main__":
    asyncio.run(main())