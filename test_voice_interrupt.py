"""Tests for voice command triage.

Covers the shared VoiceCommandProcessor: empty input is rejected,
interruption keywords report "interrupted", and everything else is a
fresh command for /api/command.
"""
import asyncio

import pytest

from backend.agent.voice import VoiceCommandProcessor


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_empty_command_rejected():
    proc = VoiceCommandProcessor()
    assert run(proc.process_command("   ", None))["status"] == "error"


@pytest.mark.parametrize("phrase", [
    "stop", "stop that right now", "quiet please",
    "that's enough", "cancel everything",
])
def test_interruption_keywords(phrase):
    proc = VoiceCommandProcessor()
    res = run(proc.process_command(phrase, None))
    assert res["status"] == "interrupted"


def test_non_interruption_is_new_command():
    proc = VoiceCommandProcessor()
    res = run(proc.process_command("what is the weather", None))
    assert res["status"] == "new_command"


def test_only_known_statuses():
    """Only the documented triage statuses are ever produced."""
    proc = VoiceCommandProcessor()
    for prompt in ("actually search for pictures of dogs",
                   "open the calculator application",
                   "take a screenshot"):
        res = run(proc.process_command(prompt, None))
        assert res["status"] in ("new_command", "interrupted", "error")


def test_set_controller_compat_noop():
    proc = VoiceCommandProcessor()
    assert proc.set_controller(object()) is None
