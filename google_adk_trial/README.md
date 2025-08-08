# OpenAI Agent SDK Trial

A minimal setup to run an agent using the OpenAI Agent SDK.

## Setup

```bash
cd ~/agent-sdk-trial/openai-agent-sdk-trial
conda create --name google-adk-trial python=3.12 -y
conda activate google-adk-trial
pip install google-adk python-dotenv boto3
pip install -U "litellm>=1.72.1"
pip install -U "litellm[proxy]>=1.72"
```

## Run

```bash
# 1. confirm local AWS profile setting
aws sso login --profile agency_admin-654654286512-ap
export AWS_PROFILE=agency_admin-654654286512-ap
aws sts get-caller-identity --profile agency_admin-654654286512-ap --region ap-southeast-1

# 2. Trun Off Cloudware WARP

# 3. Run the agent
adk run my_agent.gemini_agent
```
