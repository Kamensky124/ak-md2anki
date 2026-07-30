"""Runtime configuration via environment variables.

No secret values live here — the OpenRouter key is read from the environment at
call time (see :func:`openrouter_key`) and is never persisted by this tool.
"""

from __future__ import annotations

import os

# Deck names (override per-environment if desired).
VOCAB_DECK = os.environ.get("AK_MD2ANKI_VOCAB_DECK", "Business::Vocab")
QA_DECK = os.environ.get("AK_MD2ANKI_QA_DECK", "Business::ClientQA")

# OpenRouter enrichment.
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = os.environ.get("AK_MD2ANKI_MODEL", "openai/gpt-oss-20b:free")
FALLBACK_MODEL = os.environ.get(
    "AK_MD2ANKI_FALLBACK_MODEL", "meta-llama/llama-3.3-70b-instruct:free"
)
# House rule: keep LLM request rate modest (also respects free-model caps).
RPM_LIMIT = int(os.environ.get("AK_MD2ANKI_RPM", "5"))
ENRICH_BATCH_SIZE = int(os.environ.get("AK_MD2ANKI_BATCH", "10"))

# AnkiConnect.
ANKI_CONNECT_URL = os.environ.get("ANKI_CONNECT_URL", "http://127.0.0.1:8765")


def openrouter_key() -> str | None:
    """Return the OpenRouter API key from the environment, or None if unset."""
    value = os.environ.get("OPENROUTER_API_KEY", "").strip()
    return value or None
