"""
llm_client.py  –  Thin wrapper around OpenAI / Anthropic.
Provides a single call_llm(prompt, system) → str function.
Falls back to a pattern-only mode if no API key is configured.
"""
from __future__ import annotations

import json
import re
from typing import Any

from config import Config


# --------------------------------------------------------------------------
# Exceptions
# --------------------------------------------------------------------------

class NoLLMKeyError(RuntimeError):
    """Raised when no LLM API key is configured – triggers heuristic fallback."""


# --------------------------------------------------------------------------
# Public interface
# --------------------------------------------------------------------------

def call_llm(prompt: str, system: str, cfg: Config) -> str:
    """Return a raw string from the configured LLM (expected to be JSON)."""
    if cfg.llm_provider == "anthropic" and cfg.anthropic_api_key:
        return _anthropic(prompt, system, cfg)
    if cfg.openai_api_key:
        return _openai(prompt, system, cfg)
    raise NoLLMKeyError(
        "No LLM API key configured. Running in heuristic mode (pattern-based extraction). "
        "Set OPENAI_API_KEY or ANTHROPIC_API_KEY in .env for higher accuracy."
    )


def call_llm_json(prompt: str, system: str, cfg: Config) -> dict[str, Any]:
    """Call LLM and parse the result as JSON."""
    raw = call_llm(prompt, system, cfg)
    # Strip markdown code fences if present
    raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    return json.loads(raw)


# --------------------------------------------------------------------------
# Provider implementations
# --------------------------------------------------------------------------

def _openai(prompt: str, system: str, cfg: Config) -> str:
    try:
        from openai import OpenAI
        from openai import AuthenticationError as OAIAuthError
    except ImportError as exc:
        raise ImportError("Run: pip install openai") from exc

    try:
        client = OpenAI(api_key=cfg.openai_api_key)
        response = client.chat.completions.create(
            model=cfg.llm_model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
        )
        return response.choices[0].message.content or ""
    except OAIAuthError:
        raise NoLLMKeyError(
            "OpenAI API key is invalid or expired. Falling back to heuristic mode."
        )


def _anthropic(prompt: str, system: str, cfg: Config) -> str:
    try:
        import anthropic
        from anthropic import AuthenticationError as AnthAuthError
    except ImportError as exc:
        raise ImportError("Run: pip install anthropic") from exc

    try:
        client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            system=system + "\nAlways respond with valid JSON only.",
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    except AnthAuthError:
        raise NoLLMKeyError(
            "Anthropic API key is invalid or expired. Falling back to heuristic mode."
        )
