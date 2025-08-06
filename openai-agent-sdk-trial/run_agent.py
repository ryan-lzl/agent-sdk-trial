# run_agent.py (Final Version)

import asyncio
import os
import openai
from dotenv import load_dotenv
from agents import Agent, Runner

# --- START: CONFIGURATION FROM ENVIRONMENT ---

# 1. Load all variables from the .env file into the environment.
load_dotenv()

# 2. Read all configuration from the environment variables.
LITELLM_PROXY_URL = os.getenv("LITELLM_PROXY_URL")
PROXY_API_KEY = os.getenv("LITELLM_PROXY_API_KEY")
MODEL_ALIAS_SONNET = os.getenv("MODEL_ALIAS_SONNET") # Reads the full "litellm/..." string

# 3. Validate that all required configuration variables were found.
if not all([LITELLM_PROXY_URL, PROXY_API_KEY, MODEL_ALIAS_SONNET]):
    raise ValueError("One or more required environment variables are missing from .env file. "
                     "Please check LITELLM_PROXY_URL, LITELLM_PROXY_API_KEY, "
                     "and MODEL_ALIAS_SONNET.")

# 4. Configure the global OpenAI module to point to your LiteLLM proxy.
#    This allows the LiteLLM provider to connect to your proxy.
openai.base_url = LITELLM_PROXY_URL
openai.api_key = PROXY_API_KEY

# --- END: CONFIGURATION FROM ENVIRONMENT ---


async def main():
    """
    This function creates an agent for the Anthropic Sonnet model and sends
    the request to the LiteLLM Proxy configured in the .env file.
    """

    # Create an agent for the Anthropic Sonnet model.
    # The model string is now read directly from the .env file and already
    # contains the necessary "litellm/" prefix.
    sonnet_agent = Agent(
        name="Anthropic_Sonnet_Agent",
        instructions="You are a helpful and friendly assistant from Anthropic. Your name is Claude.",
        model=MODEL_ALIAS_SONNET
    )
    
    # Initialize the Runner with no arguments.
    # It will pick up the proxy configuration from the global openai module.
    runner = Runner()

    # We print the model alias without the prefix for clarity in the logs.
    print(f"--- Running agent with model '{MODEL_ALIAS_SONNET.split('/')[-1]}' via proxy at {LITELLM_PROXY_URL} ---")
    
    # Using a new prompt suitable for the Claude model.
    sonnet_result = await runner.run(sonnet_agent, "Explain the concept of 'Constitutional AI' in a few sentences.")
    
    if sonnet_result.final_output:
        print(sonnet_result.final_output)
    else:
        print("The Sonnet agent did not produce a final output.")
        if sonnet_result.error:
            print(f"Error: {sonnet_result.error}")


if __name__ == "__main__":
    asyncio.run(main())