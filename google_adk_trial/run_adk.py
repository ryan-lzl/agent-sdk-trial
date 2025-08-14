#!/usr/bin/env python3
"""
Run the ADK CLI under a pseudo-terminal (PTY) so prompts render at the right
time, while filtering only the noisy UserWarnings and collapsing any repeated
[user]: prompts.

Fixes:
- Remove unsupported pty.spawn(env=...) usage; set env on os.environ instead.
- Do chunk-level filtering (not line-buffered) so a prompt printed without a
  trailing newline still appears immediately.
- Collapse sequences like "[user]: [user]: [user]:" into a single "[user]: ".
- Hide only the specific UserWarning lines you asked to suppress.
"""

import os
import re
import sys
import pty

# Hide only these warnings
HIDE_PATTERNS = (
    "UserWarning: [EXPERIMENTAL] InMemoryCredentialService",
    "UserWarning: [EXPERIMENTAL] BaseCredentialService",
    'UserWarning: Field name "config_type" in "SequentialAgent" shadows an attribute in parent "BaseAgent"',
)

# Collapse any burst of 2+ prompts into a single prompt token
PROMPT_SEQ_RE = re.compile(r'(?:\s*\[user\]:\s*){2,}')

def _filter_chunk(text: str) -> str:
    """
    Filter a chunk of ADK output:
      - drop lines matching HIDE_PATTERNS,
      - collapse duplicate [user]: prompts,
      - otherwise pass through unchanged.
    Chunk-level so prompts without trailing newline still render.
    """
    # Remove only whole lines that contain the unwanted warnings
    out_parts = []
    for part in text.splitlines(keepends=True):
        if any(pat in part for pat in HIDE_PATTERNS):
            # drop this warning line
            continue
        out_parts.append(part)
    out_text = "".join(out_parts)

    # Collapse repeated [user]: prompts anywhere in the chunk
    out_text = PROMPT_SEQ_RE.sub("[user]: ", out_text)

    return out_text

def master_read(fd: int) -> bytes:
    """Read from child PTY, filter, and return bytes for stdout."""
    try:
        data = os.read(fd, 4096)
    except OSError:
        return b""
    if not data:
        return b""

    try:
        text = data.decode("utf-8", errors="ignore")
    except Exception:
        text = data.decode(errors="ignore")

    filtered = _filter_chunk(text)
    return filtered.encode("utf-8")

def main():
    # Ensure child Python ignores warnings too (belt & suspenders)
    os.environ["PYTHONWARNINGS"] = "ignore"

    # Spawn ADK CLI under this interpreter in a PTY (correct interactive behavior)
    argv = (sys.executable, "-W", "ignore", "-m", "google.adk.cli", "run", ".")
    pty.spawn(argv, master_read=master_read)

if __name__ == "__main__":
    main()
