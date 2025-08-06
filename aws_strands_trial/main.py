import os
from dotenv import load_dotenv
from strands import Agent
from strands.models.litellm import LiteLLMModel

def main():
    """
    Demonstrates the use of AWS Strands with LiteLLM to interact with
    OpenAI and Google Gemini models within a Conda environment.
    """
    # Load environment variables from the .env file
    load_dotenv()

    # --- 1. Verify API Keys are Loaded ---
    if "OPENAI_API_KEY" not in os.environ or "GEMINI_API_KEY" not in os.environ:
        print("Error: API keys not found.")
        print("Please ensure you have a .env file with OPENAI_API_KEY and GEMINI_API_KEY.")
        return

    print("API keys loaded successfully.")

    # --- 2. Initialize Models using LiteLLM ---
    # LiteLLM automatically uses the API keys from the environment variables

    # Initialize the OpenAI GPT-4o model
    openai_model = LiteLLMModel(
        model="openai/gpt-4o"
    )

    # Initialize the Google Gemini 2.5 Pro model
    # Note: Using a more recent Gemini model for this example
    gemini_model = LiteLLMModel(
        model="gemini/gemini-2.5-pro-latest"
    )

    # --- 3. Create AWS Strands Agents for each model ---

    # Create an agent that uses the OpenAI model
    openai_agent = Agent(
        model=openai_model,
        system_prompt="You are a helpful assistant powered by OpenAI's GPT-3.5 Turbo."
    )

    # Create an agent that uses the Google Gemini model
    gemini_agent = Agent(
        model=gemini_model,
        system_prompt="You are a helpful assistant powered by Google's Gemini 1.5 Pro."
    )

    # --- 4. Interact with the Agents ---
    user_prompt = "What are the key benefits of using a model-agnostic agent SDK?"

    print("\n--- Interacting with OpenAI Agent ---")
    try:
        openai_response = openai_agent.invoke(user_prompt)
        print(f"OpenAI Agent: {openai_response.content}\n")
    except Exception as e:
        print(f"An error occurred with the OpenAI agent: {e}\n")


    print("--- Interacting with Google Gemini Agent ---")
    try:
        gemini_response = gemini_agent.invoke(user_prompt)
        print(f"Gemini Agent: {gemini_response.content}")
    except Exception as e:
        print(f"An error occurred with the Gemini agent: {e}")


if __name__ == "__main__":
    main()