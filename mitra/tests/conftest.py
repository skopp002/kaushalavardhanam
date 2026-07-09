"""Shared fixtures: package bootstrap + fakes (DESIGN §9)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_ROOT = Path(__file__).resolve().parents[1]

try:
    import mitra  # noqa: F401  (pip-installed)
except ImportError:  # run from the repo checkout: alias src/ as the mitra package
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "mitra", _ROOT / "src" / "__init__.py",
        submodule_search_locations=[str(_ROOT / "src")],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["mitra"] = module
    spec.loader.exec_module(module)

from mitra.lexicon.store import LexiconStore  # noqa: E402
from mitra.robot.reachy import FakeReachy  # noqa: E402


class FakeTTS:
    """Records synthesized text; returns 0.1 s of silence."""

    def __init__(self):
        self.spoken: list[str] = []

    def synthesize(self, text: str):
        self.spoken.append(text)
        return np.zeros(1600, dtype=np.float32), 16000


class CannedAgent:
    """Returns queued replies in order; records every prompt it gets."""

    def __init__(self, replies=()):
        self.replies = list(replies)
        self.calls: list[str] = []
        self.resets = 0

    def converse(self, message: str) -> str:
        self.calls.append(message)
        return self.replies.pop(0) if self.replies else "अस्तु।"

    def reset(self) -> None:
        self.resets += 1


@pytest.fixture
def fake_robot():
    return FakeReachy()


@pytest.fixture
def fake_tts():
    return FakeTTS()


@pytest.fixture
def lexicon():
    return LexiconStore(":memory:")


@pytest.fixture
def make_orchestrator(fake_robot, fake_tts, lexicon):
    """Factory: orchestrator wired with fakes; tests drive handle_event()."""
    from mitra.orchestrator import Orchestrator

    def _make(replies=(), **kwargs):
        agent = CannedAgent(replies)
        orch = Orchestrator(robot=fake_robot, agent=agent, tts=fake_tts,
                            lexicon=lexicon, **kwargs)
        return orch, agent

    return _make
