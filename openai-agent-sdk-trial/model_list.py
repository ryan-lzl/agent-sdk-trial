import openai
import os
import json
from dotenv import load_dotenv
import requests # Import the requests library

# Load environment variables from the .env file
load_dotenv()

# --- Retrieve configuration from environment variables ---
proxy_url = os.getenv("LITELLM_PROXY_URL")
api_key = os.getenv("LITELLM_PROXY_API_KEY")
model_sonnet = os.getenv("MODEL_ALIAS_SONNET")

# --- Method 1: Direct API Call using the `requests` library ---
print("--- Calling /v1/models directly using `requests` ---")

if not all([proxy_url, api_key]):
    print("Error: Missing PROXY_URL or API_KEY for direct call.")
else:
    try:
        # 1. Construct the full URL for the models endpoint
        # Make sure the proxy_url does not end with a slash to avoid double slashes
        models_url = f"{proxy_url.rstrip('/')}/v1/models"

        # 2. Set up the required headers for authentication
        # The API key is sent as a Bearer token in the Authorization header
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        # 3. Make the HTTP GET request
        print(f"Making GET request to: {models_url}")
        response = requests.get(models_url, headers=headers)

        # 4. Check for errors (e.g., 401 Unauthorized, 404 Not Found)
        response.raise_for_status() 

        # 5. Parse the JSON response and pretty-print it
        models_data = response.json()
        print(json.dumps(models_data, indent=2))

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        print(f"Response content: {response.text}")
    except Exception as e:
        print(f"An other error occurred: {e}")

print("\n" + "="*50 + "\n")

# --- Method 2: Using the OpenAI Client Library (for comparison) ---
print("--- Calling models using the `openai` client library ---")

if not all([proxy_url, api_key, model_sonnet]):
    print("Error: Missing one or more environment variables for OpenAI client.")
else:
    client = openai.OpenAI(api_key=api_key, base_url=proxy_url)
    try:
        model_list = client.models.list()
        models_dict = [model.dict() for model in model_list.data]
        print(json.dumps(models_dict, indent=2))
    except Exception as e:
        print(f"An error occurred while fetching models: {e}")