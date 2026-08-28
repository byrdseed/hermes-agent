"""Automatic compression must warn once, then pause with HST time."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from agent.context_compressor import ContextCompressor
from agent.conversation_compression import (
    COMPRESSION_COMING_SOON_STATUS as SOON,
    consider_compression_coming_soon as consider,
    emit_automatic_compression_notices,
    format_compression_pause_status,
)

PAUSE = "Pause! We are compressing at 3:42 PM HST"


def _agent(threshold=1000, enabled=True, emit=True, engine=None):
    events = []
    engine = engine or SimpleNamespace(
        threshold_tokens=threshold, emit_automatic_compaction_status=emit,
        _compression_coming_soon_latched=False,
    )
    agent = SimpleNamespace(compression_enabled=enabled, context_compressor=engine, events=events)
    agent._emit_status = events.append
    return agent

def test_warning_band_emits_once_and_resets():
    agent = _agent()
    consider(agent, 899)
    assert agent.events == []
    consider(agent, 900)
    consider(agent, 999)
    assert agent.events == [SOON]
    with patch("agent.context_compressor.get_model_context_length", return_value=100_000):
        engine = ContextCompressor(model="m", quiet_mode=True)
    engine.threshold_tokens = 1000
    agent = _agent(engine=engine)
    consider(agent, 900)
    engine.record_completed_compaction()
    consider(agent, 910)
    engine.on_session_reset()
    consider(agent, 920)
    assert agent.events == [SOON, SOON, SOON]

def test_jump_emits_warning_before_pause():
    agent = _agent()
    with patch("agent.conversation_compression.format_compression_pause_status", return_value=PAUSE):
        emit_automatic_compression_notices(agent, tokens=50)
    assert agent.events == [SOON, PAUSE]

def test_pause_status_uses_pinned_hst_clock():
    assert format_compression_pause_status(datetime(2026, 8, 28, 1, 42, tzinfo=timezone.utc)) == PAUSE

def test_disabled_threshold_and_plugin_suppress_stay_silent():
    for agent in (_agent(enabled=False), _agent(threshold=0), _agent(emit=False)):
        consider(agent, 950)
        assert agent.events == []
    plugin = _agent(emit=False)
    emit_automatic_compression_notices(plugin, tokens=2000)
    assert plugin.events == []
