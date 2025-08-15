# tools/fetch_and_summarize.py
from typing import Dict, Any
import requests
from bs4 import BeautifulSoup

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "fetch_and_summarize",
        "description": "Fetch a web page and return cleaned plain text for summarization.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "HTTP/HTTPS URL to fetch"},
                "timeout_sec": {
                    "type": "integer", "minimum": 1, "maximum": 60, "default": 10
                },
                "max_chars": {
                    "type": "integer", "minimum": 1000, "maximum": 40000, "default": 6000
                },
            },
            "required": ["url"],
            "additionalProperties": False,
        },
    },
}

def run(url: str, timeout_sec: int = 10, max_chars: int = 6000) -> str:
    headers = {"User-Agent": "m365-agents-sdk-sample/1.0 (+lite-llm-proxy)"}
    r = requests.get(url, headers=headers, timeout=timeout_sec)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
        tag.extract()

    text = " ".join(soup.get_text(separator=" ").split())
    return text[:max_chars] + (" ...[truncated]" if len(text) > max_chars else "")
