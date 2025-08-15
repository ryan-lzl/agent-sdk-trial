from __future__ import annotations
import re
from urllib.parse import urlparse
from typing import Dict, Any, Optional

import requests
from bs4 import BeautifulSoup, UnicodeDammit

# How much text we aim for before truncation
DEFAULT_MAX_CHARS = 10_000
MIN_REASONABLE_CHARS = 1_200  # if below, use aggressive fallback extraction

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "fetch_and_summarize",
        "description": "Fetch a public web page and return cleaned/plain text for summarization.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The full URL to fetch (http/https).",
                },
                "timeout_sec": {
                    "type": "integer",
                    "description": "HTTP timeout in seconds (default: 12).",
                    "minimum": 1,
                    "maximum": 60,
                },
                "max_chars": {
                    "type": "integer",
                    "description": f"Truncate cleaned text to this many characters (default: {DEFAULT_MAX_CHARS}).",
                    "minimum": 500,
                    "maximum": 100_000,
                },
            },
            "required": ["url"],
            "additionalProperties": False,
        },
    },
}

def _normalize_url(u: str) -> str:
    """
    Correct common URL typos:
      - https.www.example.com  -> https://www.example.com
      - https//example.com     -> https://example.com
      - https:/example.com     -> https://example.com
      - www.example.com        -> https://www.example.com
      - https://https.www.x    -> https://www.x
    """
    if not u:
        return u
    u = u.strip().strip('"\'')

    # Remove spaces
    u = u.replace(" ", "")

    # Fix missing colon or slash variations
    u = re.sub(r'^(https?)(//)(?!/)', r'\1://', u)        # https//x -> https://x
    u = re.sub(r'^(https?):/([^/])', r'\1://\2', u)       # https:/x  -> https://x

    # Fix "https.www..." or "http.www..."
    u = re.sub(r'^(https?)\.(?=[^/])', r'\1://', u)       # https.www -> https://www

    # If it starts with www., prepend https://
    if u.startswith("www."):
        u = "https://" + u

    # If still missing a scheme, default to https://
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*://', u):
        u = "https://" + u

    # Collapse accidental double scheme like "https://https.www..."
    u = u.replace("https://https.", "https://").replace("http://http.", "http://")

    # Final sanity via urlparse; if netloc is still empty, try treating path as host
    p = urlparse(u)
    if not p.netloc:
        if p.path:
            candidate = "https://" + p.path
            p2 = urlparse(candidate)
            if p2.netloc:
                return candidate
    return u

def _decode_html(content: bytes, declared_encoding: Optional[str]) -> str:
    """
    Use UnicodeDammit to robustly decode HTML bytes (fixes stray Â, smart quotes, etc.).
    """
    if declared_encoding:
        try:
            return content.decode(declared_encoding, errors="replace")
        except Exception:
            pass
    dammit = UnicodeDammit(content, is_html=True)
    return dammit.unicode_markup or content.decode("utf-8", errors="replace")

def _visible_text_first_pass(soup: BeautifulSoup) -> str:
    """
    Prefer textual content from main content selectors; keep <noscript>.
    """
    # Remove obviously non-content tags (keep <noscript>)
    for tag in soup(["script", "style", "svg", "iframe", "canvas", "form"]):
        tag.decompose()

    # Remove site chrome if present
    for sel in ["header", "footer", "nav", "[role=navigation]", ".cookie", ".cookie-banner", ".consent"]:
        for t in soup.select(sel):
            t.decompose()

    root = soup.find(["main", "article"]) or soup.body or soup
    # Collect headings + paragraphs + list items
    chunks = [el.get_text(" ", strip=True) for el in root.select("h1,h2,h3,p,li") if el.get_text(strip=True)]
    text = "\n".join(chunks)

    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def _aggressive_fallback(soup: BeautifulSoup) -> str:
    """
    Fallback: get as much visible text as possible from <body>.
    """
    body = soup.body or soup
    text = body.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def run(url: str, timeout_sec: int = 12, max_chars: int = DEFAULT_MAX_CHARS) -> str:
    """
    Fetch the page at `url`, return cleaned plain text (truncated to max_chars).
    Robust decoding + two-pass extraction yields enough text in one shot.
    """
    try:
        norm = _normalize_url(url)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        r = requests.get(norm, headers=headers, timeout=timeout_sec, allow_redirects=True)
        r.raise_for_status()

        # Robust decode (fixes mis-encoded chars like Â)
        html = _decode_html(r.content, r.encoding or None)

        # Parse and extract
        soup = BeautifulSoup(html, "html.parser")
        text = _visible_text_first_pass(soup)

        if len(text) < MIN_REASONABLE_CHARS:
            # Try aggressive fallback over full body text
            text2 = _aggressive_fallback(soup)
            # Choose the longer non-empty result
            if len(text2) > len(text):
                text = text2

        # Final trim
        cap = max_chars if max_chars and max_chars > 0 else DEFAULT_MAX_CHARS
        if len(text) > cap:
            text = text[:cap] + "…"

        return text if text else "ERROR: No visible text found."

    except requests.exceptions.RequestException as e:
        return f"ERROR: HTTP request failed: {e}"
    except Exception as e:
        return f"ERROR: {e}"
