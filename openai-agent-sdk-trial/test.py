import openai
import os
from dotenv import load_dotenv


client = openai.OpenAI(
    api_key="sk--2Az8wLKRCJiw5XVzj53Xw",
    base_url="https://litellm-stg.aip.gov.sg"
)

response = client.chat.completions.create(
    model="anthropic.claude-3-5-sonnet-20240620-v1:0", # model to send to the proxy
    messages = [
        {
            "role": "user",
            "content": "this is a test request, write a short poem"
        }
    ]
)
print(response)