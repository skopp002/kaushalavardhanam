"""Conversation-history trimming (src/agent/agent.py).

Strands is an optional extra, so these drive the trimming logic against a stub
that mimics the provider message shape rather than constructing a real Agent.
"""

from __future__ import annotations

from mitra.agent.agent import MitraAgent


class _StubAgent:
    def __init__(self, messages):
        self.messages = messages


def _mk(n):
    """n user/assistant exchanges as plain text messages."""
    out = []
    for i in range(n):
        out.append({"role": "user", "content": [{"text": f"q{i}"}]})
        out.append({"role": "assistant", "content": [{"text": f"a{i}"}]})
    return out


def _trimmer(messages, turns=4):
    agent = MitraAgent.__new__(MitraAgent)
    agent.max_history_turns = turns
    agent._agent = _StubAgent(messages)
    return agent


def test_short_history_untouched():
    agent = _trimmer(_mk(3))
    agent._trim_history()
    assert len(agent._agent.messages) == 6


def test_long_history_trimmed_to_window():
    agent = _trimmer(_mk(10))
    agent._trim_history()
    assert len(agent._agent.messages) == 8


def test_trim_keeps_the_most_recent_turns():
    agent = _trimmer(_mk(10))
    agent._trim_history()
    assert agent._agent.messages[-1]["content"][0]["text"] == "a9"


def test_window_starts_on_a_user_turn():
    agent = _trimmer(_mk(10))
    agent._trim_history()
    assert agent._agent.messages[0]["role"] == "user"


def test_window_never_opens_on_an_orphaned_tool_result():
    """A toolResult without its toolUse is a malformed conversation."""
    messages = _mk(4)
    messages.insert(-1, {"role": "user",
                         "content": [{"toolResult": {"content": []}}]})
    agent = _trimmer(messages, turns=2)
    agent._trim_history()
    first = agent._agent.messages[0]
    assert first["role"] == "user"
    assert not any("toolResult" in b for b in first["content"])


def test_zero_disables_trimming():
    agent = _trimmer(_mk(10), turns=0)
    agent._trim_history()
    assert len(agent._agent.messages) == 20


def test_unexpected_message_shape_leaves_history_alone():
    agent = _trimmer("not a list")
    agent._trim_history()
    assert agent._agent.messages == "not a list"


# ------------------------------------------- running out of context (FR-6.4)

class MaxTokensReachedException(Exception):
    """Same name as the Strands exception, which is an optional import."""


class _RunawayAgent(_StubAgent):
    """Stops mid-sentence and leaves the partial message in history, as
    Strands does when Ollama reports ``done_reason: length``."""

    def __call__(self, message):
        self.messages.append({"role": "user", "content": [{"text": message}]})
        self.messages.append(
            {"role": "assistant", "content": [{"text": "The verse says that"}]})
        raise MaxTokensReachedException("out of room")


def _agent_over_stub(stub):
    agent = MitraAgent.__new__(MitraAgent)
    agent.max_history_turns = 4
    agent._agent = stub
    return agent


def test_a_truncated_reply_is_spoken_rather_than_lost():
    agent = _agent_over_stub(_RunawayAgent(_mk(1)))
    assert agent.converse("What does that mean?") == "The verse says that"


def test_the_half_finished_message_does_not_stay_in_history():
    """It made the following reply English too, and the gate failed it twice."""
    stub = _RunawayAgent(_mk(1))
    agent = _agent_over_stub(stub)
    agent.converse("What does that mean?")
    assert all(m["content"][0]["text"] != "The verse says that"
               for m in stub.messages)


def test_any_other_failure_still_reaches_the_orchestrator():
    class _Broken(_StubAgent):
        def __call__(self, message):
            raise RuntimeError("ollama is down")

    agent = _agent_over_stub(_Broken([]))
    try:
        agent.converse("hello")
    except RuntimeError:
        return
    raise AssertionError("the failure was swallowed")
