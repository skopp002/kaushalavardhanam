"""Strands Agent construction (DESIGN §1.3–1.5).

Provider selection is config-driven: local Ollama (Qwen3-VL) by default;
anthropic/bedrock is the Option B one-line swap (FR-6.3). The Strands Agent
owns the conversation loop, message history, and tool dispatch.
"""

from __future__ import annotations

import json
import urllib.request

from .prompts import SANSKRIT_SYSTEM_PROMPT


class MitraAgent:
    def __init__(self, llm_config: dict, tools: list,
                 system_prompt: str = SANSKRIT_SYSTEM_PROMPT, verbose: bool = True):
        self._llm_config = llm_config
        try:
            from strands import Agent
        except ImportError as e:
            raise ImportError(
                "strands-agents is required for the agent layer. "
                "Install with: pip install 'mitra[agent]'"
            ) from e
        # Strands' default callback handler streams reply tokens straight to
        # stdout — set verbose=False (e.g. in batch/test scripts) to silence
        # it and get only the final string from converse().
        agent_kwargs = {} if verbose else {"callback_handler": None}
        self._agent = Agent(
            model=self._make_model(llm_config),
            tools=tools,
            system_prompt=system_prompt,
            **agent_kwargs,
        )

    @staticmethod
    def _make_model(cfg: dict):
        provider = cfg.get("provider", "ollama")
        if provider == "ollama":
            from strands.models.ollama import OllamaModel

            return OllamaModel(
                host=cfg.get("host", "http://localhost:11434"),
                model_id=cfg.get("id", "qwen3-vl:8b"),
                temperature=cfg.get("temperature", 0.3),
                keep_alive=cfg.get("keep_alive", "30m"),
                # Qwen3-VL defaults to thinking mode in Ollama, which burns the
                # latency budget and can leave the reply empty — keep it off.
                additional_args={"think": cfg.get("think", False)},
            )
        if provider == "anthropic":
            from strands.models.anthropic import AnthropicModel

            return AnthropicModel(model_id=cfg["id"])
        if provider == "bedrock":
            from strands.models import BedrockModel

            return BedrockModel(model_id=cfg["id"])
        raise ValueError(f"unknown LLM provider: {provider!r}")

    def converse(self, message: str) -> str:
        """One turn: user message in, final agent text out (tools may run)."""
        return str(self._agent(message)).strip()

    def warmup(self) -> None:
        """Load the configured local model without invoking its tool loop."""
        self.warmup_model(self._llm_config)

    @staticmethod
    def warmup_model(cfg: dict) -> None:
        """Warm an Ollama model with one token and no agent tools."""
        if cfg.get("provider", "ollama") != "ollama":
            return
        host = cfg.get("host", "http://localhost:11434").rstrip("/")
        payload = json.dumps({
            "model": cfg.get("id", "qwen3-vl:8b"),
            "prompt": "Warm up.",
            "stream": False,
            "keep_alive": cfg.get("keep_alive", "30m"),
            "think": False,
            "options": {"num_predict": 1},
        }).encode("utf-8")
        request = urllib.request.Request(
            f"{host}/api/generate", data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            json.load(response)

    def reset(self) -> None:
        """Drop conversation history at session end (FR-3.3: per-session context)."""
        self._agent.messages = []
