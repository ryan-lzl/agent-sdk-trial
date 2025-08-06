# OpenAI Agent SDK Trial

A minimal setup to run an agent using the OpenAI Agent SDK.

## Setup

```bash
cd ~/agent-sdk-trial/openai-agent-sdk-trial
conda create --name openai-agents-env python=3.11
conda activate openai-agents-env
pip install "openai-agents[litellm]" litellm python-dotenv boto3
```

## Run

```bash
python run_agent.py
```
