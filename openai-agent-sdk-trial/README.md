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
# 1. confirm local AWS profile setting
aws sso login --profile agency_admin-654654286512-ap
export AWS_PROFILE=agency_admin-654654286512-ap
aws sts get-caller-identity --profile agency_admin-654654286512-ap --region ap-southeast-1

# 2. Trun Off Cloudware WARP

# 3. get the model list
python model_list.py

# 4. Run the agent
python run_agent.py
```
