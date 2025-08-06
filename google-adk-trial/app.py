import os
import asyncio
from dotenv import load_dotenv

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

# This command loads the API keys from your .env file into the environment
print("Loading API keys from .env file...")
load_dotenv()
print("API keys loaded.")

async def main():
    """
    This function demonstrates how to use different LLMs with Google ADK
    and LiteLLM within a Conda environment.
    """

    # --- 1. Using an OpenAI Model ---
    print("\n--- Initializing Agent with OpenAI Model ---")
    try:
        # Instantiate the LiteLlm wrapper for the desired OpenAI model
        openai_model = LiteLlm(model="openai/gpt-3.5-turbo")

        # Create an ADK agent using the OpenAI model
        openai_agent = LlmAgent(
            model=openai_model,
            instructions="You are a helpful assistant powered by an OpenAI model. Introduce yourself.",
        )

        print("--- Interacting with the OpenAI Agent ---")
        async for event in openai_agent.run(request="Hello!"):
            if event.type == "llm_response":
                print(f"OpenAI Agent: {event.content}")

    except Exception as e:
        print(f"Error while running OpenAI agent: {e}")
        print("Please ensure your OPENAI_API_KEY is set correctly in the .env file.")


    print("\n" + "="*50 + "\n")


    # --- 2. Using a Google Gemini Model ---
    print("--- Initializing Agent with Google Gemini Model ---")
    try:
        # Instantiate the LiteLlm wrapper for the desired Google Gemini model.
        # The model name "gemini/gemini-pro" is a standard identifier in LiteLLM.
        # We use it here instead of the hypothetical "2.5 Pro".
        gemini_model = LiteLlm(model="gemini/gemini-pro")

        # Create an ADK agent using the Gemini model
        gemini_agent = LlmAgent(
            model=gemini_model,
            instructions="You are a friendly assistant powered by Google's Gemini Pro model. Introduce yourself.",
        )

        print("--- Interacting with the Gemini Agent ---")
        async for event in gemini_agent.run(request="Hello there!"):
            if event.type == "llm_response":
                print(f"Gemini Agent: {event.content}")

    except Exception as e:
        print(f"Error while running Gemini agent: {e}")
        print("Please ensure your GEMINI_API_KEY is set correctly in the .env file.")


if __name__ == "__main__":
    # Python 3.8+ for asyncio.run()
    asyncio.run(main())