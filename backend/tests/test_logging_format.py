"""Log lines are one clean line each, tagged with the run they belong to."""

from __future__ import annotations

import logging
from types import SimpleNamespace as Obj

import pytest

from clients.ai.base import reply_text
from core.api_log_middleware import _level
from core.logging_config import ContextFormatter
from usage.context import llm_scope
from usage.recorder import _usage_summary


def _format(message: str, *args, **extra) -> str:
    record = logging.LogRecord("pipeline.service", logging.INFO, __file__, 1, message, args, None)
    record.__dict__.update(extra)
    return ContextFormatter("%(message)s").format(record)


def test_a_line_outside_a_run_has_no_tag():
    assert _format("Worker started") == "Worker started"


def test_lines_in_a_run_carry_project_and_step():
    with llm_scope(project_id="ccfd03f4-4132-4a3c", step="transcription"):
        assert _format("TRANSCRIBED %d words", 120) == "[ccfd03f4 transcription] TRANSCRIBED 120 words"


def test_explicit_project_and_step_win_and_are_not_repeated_as_fields():
    line = _format("STEP 1/2 START", project_id="abcdef123456", step="scoring", clips=3)
    assert line == "[abcdef12 scoring] STEP 1/2 START | clips=3"


def test_multi_line_messages_are_folded_onto_one_line():
    assert _format("first\n   second\nthird") == "first second third"


def test_ai_reply_text_covers_text_and_tool_calls():
    openai_style = {"choices": [{"message": {"content": "ok", "tool_calls": [{"function": {"name": "cut", "arguments": "{}"}}]}}]}
    assert reply_text(openai_style) == "ok tool cut({})"
    anthropic_style = Obj(content=[Obj(type="text", text="hi"), Obj(type="tool_use", name="pick", input={"i": 1})])
    assert reply_text(anthropic_style) == 'hi tool pick({"i": 1})'


def test_usage_summary_shows_only_what_the_call_used():
    assert _usage_summary(1200, 340, 0, 0, None, None) == "in=1200 out=340"
    assert _usage_summary(10, 5, 800, 0, None, None) == "in=10 out=5 cache_read=800"
    assert _usage_summary(0, 0, 0, 0, 312.04, None) == "audio=312.0s"


@pytest.mark.parametrize(("path", "status", "level"), [
    ("/api/v1/pipeline/status/p1", 200, logging.DEBUG),
    ("/api/v1/clips/progress/p1", 200, logging.DEBUG),
    ("/api/v1/pipeline/status/p1", 404, logging.INFO),
    ("/api/v1/pipeline/start/p1", 200, logging.INFO),
    ("/api/v1/me", 500, logging.WARNING),
])
def test_successful_polls_are_quiet_and_failures_are_not(path, status, level):
    assert _level(path, status) == level
