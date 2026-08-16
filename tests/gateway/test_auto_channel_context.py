"""End-to-end gateway tests for Slack topic-selected session context."""

import sys
import types
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

import gateway.run as gateway_run
from gateway.config import GatewayConfig, Platform
from gateway.platforms.base import MessageEvent
from gateway.session import SessionEntry, SessionSource


SESSION_KEY = "agent:main:slack:channel:C123"


def _source():
    return SessionSource(
        platform=Platform.SLACK,
        chat_id="C123",
        chat_type="channel",
        chat_name="curriculum",
        user_id="U123",
    )


def _event():
    return MessageEvent(
        text="Handle this request",
        source=_source(),
        message_id="171234.0001",
        auto_context="[Channel context: curriculum.md]\nUse curriculum rules.",
    )


def _entry(*, new=False, fresh_reset=False, auto_reset=False):
    now = datetime.now()
    return SessionEntry(
        session_key=SESSION_KEY,
        session_id="sess-context",
        created_at=now - (timedelta(seconds=1) if not new else timedelta()),
        updated_at=now,
        platform=Platform.SLACK,
        chat_type="channel",
        is_fresh_reset=fresh_reset,
        was_auto_reset=auto_reset,
    )


def _bootstrap(monkeypatch, tmp_path, entries):
    fake_dotenv = types.ModuleType("dotenv")
    fake_dotenv.load_dotenv = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "dotenv", fake_dotenv)

    runner = gateway_run.GatewayRunner(GatewayConfig())
    runner.adapters = {}
    runner._running_agents = {}
    runner._running_agents_ts = {}
    runner._pending_messages = {}
    runner._pending_approvals = {}
    runner._is_user_authorized = lambda _source: True
    runner._set_session_env = lambda _context: None
    runner._handle_active_session_busy_message = AsyncMock(return_value=False)
    runner._session_db = None
    runner._recover_telegram_topic_thread_id = lambda _source: None
    runner._cache_session_source = lambda _key, _source: None
    runner._is_session_run_current = lambda _key, _gen: True
    runner._reply_anchor_for_event = lambda _event: None
    runner._get_guild_id = lambda _event: None
    runner._should_send_voice_reply = lambda *_a, **_kw: False
    runner.hooks = MagicMock()
    runner.hooks.emit = AsyncMock()

    runner.session_store = MagicMock()
    runner.session_store.get_or_create_session.side_effect = entries
    runner.session_store.load_transcript.return_value = []
    runner.session_store.append_to_transcript = MagicMock()
    runner.session_store.has_platform_message_id.return_value = False
    runner.session_store.update_session = MagicMock()
    runner._run_agent = AsyncMock(
        return_value={
            "failed": True,
            "final_response": None,
            "error": "temporary test failure",
            "messages": [],
            "history_offset": 0,
            "last_prompt_tokens": 0,
        }
    )

    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    monkeypatch.setattr(
        gateway_run, "_resolve_runtime_agent_kwargs", lambda: {"api_key": "fake"}
    )
    monkeypatch.setattr(
        "agent.model_metadata.get_model_context_length",
        lambda *_args, **_kwargs: 100_000,
    )
    return runner


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "entry",
    [
        _entry(new=True),
        _entry(fresh_reset=True),
        _entry(auto_reset=True),
    ],
)
async def test_context_reaches_first_gateway_turn_and_transcript(
    monkeypatch, tmp_path, entry
):
    runner = _bootstrap(monkeypatch, tmp_path, [entry])

    await runner._handle_message_with_agent(_event(), _source(), SESSION_KEY, 1)

    message = runner._run_agent.await_args.kwargs["message"]
    assert message.startswith("[Channel context: curriculum.md]")
    assert message.count("[Channel context: curriculum.md]") == 1
    user_rows = [
        call.args[1]
        for call in runner.session_store.append_to_transcript.call_args_list
        if len(call.args) > 1 and call.args[1].get("role") == "user"
    ]
    assert any("[Channel context: curriculum.md]" in row["content"] for row in user_rows)


@pytest.mark.asyncio
async def test_context_is_omitted_from_ongoing_gateway_turn(monkeypatch, tmp_path):
    runner = _bootstrap(monkeypatch, tmp_path, [_entry()])

    await runner._handle_message_with_agent(_event(), _source(), SESSION_KEY, 1)

    message = runner._run_agent.await_args.kwargs["message"]
    assert message == "Handle this request"
    user_rows = [
        call.args[1]
        for call in runner.session_store.append_to_transcript.call_args_list
        if len(call.args) > 1 and call.args[1].get("role") == "user"
    ]
    assert all("[Channel context: curriculum.md]" not in row["content"] for row in user_rows)
