import os
import uuid
from dotenv import load_dotenv

load_dotenv()

from langchain_litellm import ChatLiteLLM
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import HumanMessage

# --- LiteLLM Proxy envs ---
api_base = os.getenv("LITELLM_PROXY_API_BASE", "")
api_key = os.getenv("LITELLM_PROXY_API_KEY", "")
model_id = os.getenv("LITELLM_MODEL_ID", "azure/gpt-5-chat-eastus2")

# Force routing via LiteLLM proxy
if not model_id.startswith("litellm_proxy/"):
    model_id = f"litellm_proxy/{model_id}"

# --- LLM with streaming enabled ---
llm = ChatLiteLLM(
    model=model_id,
    api_base=api_base,
    api_key=api_key,
    streaming=True,  # stream tokens to stdout via callback
)

# --- LangGraph agent with in-memory checkpointer ---
checkpoint = InMemorySaver()
agent = create_react_agent(
    llm,
    tools=[],  # pure chatbot
    prompt="You are a helpful, concise assistant.",
    checkpointer=checkpoint,
)

# One session/thread id for this CLI run (required by checkpointer)
session_id = os.getenv("SESSION_ID", str(uuid.uuid4())[:8])

print("LangGraph chatbot is running. Type your questions (or 'exit' to quit).")
print(f"[session thread_id: {session_id}]")

while True:
    try:
        user_input = input("User: ")
    except (EOFError, KeyboardInterrupt):
        print()  # clean newline on Ctrl-D/C
        break

    if user_input.strip().lower() in {"exit", "quit"}:
        break

    # Build message list
    messages = [HumanMessage(content=user_input)]

    # Streaming tokens to stdout via callback; do NOT reprint final text
    cfg = {
        "configurable": {"thread_id": session_id},
        "callbacks": [StreamingStdOutCallbackHandler()],
    }

    # Label once, then stream; no second print of the same answer
    print("Assistant: ", end="", flush=True)
    agent.invoke({"messages": messages}, config=cfg)
    print()  # newline after streaming
