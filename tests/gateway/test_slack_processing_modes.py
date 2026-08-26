import asyncio
from types import SimpleNamespace

import pytest

from gateway.platforms.base import ProcessingPhase
from gateway.run import TurnRunner
from gateway.turn_context import TurnContext


class RecordingPhaseAdapter:
    def __init__(self):
        self.phases = []

    async def set_processing_phase(
        self, channel_id, message_id, phase, scope_id=""
    ):
        self.phases.append((channel_id, message_id, phase, scope_id))
        return True


@pytest.mark.asyncio
async def test_turn_runner_emits_semantic_thinking_and_tool_phases():
    adapter = RecordingPhaseAdapter()
    source = SimpleNamespace(
        chat_id="C123",
        user_id="U123",
        scope_id="T123",
        platform=SimpleNamespace(value="slack"),
    )
    ctx = TurnContext(
        source=source,
        event_message_id="1000.1",
        _run_still_current=lambda: True,
        _processing_phase_adapter=adapter,
        _loop_for_step=asyncio.get_running_loop(),
        _hooks_ref=None,
    )
    turn_runner = TurnRunner(SimpleNamespace(), ctx)

    turn_runner._step_callback_sync(1, [])
    await asyncio.sleep(0.01)
    turn_runner.progress_callback("tool.started", "terminal", None, {})
    await asyncio.sleep(0.01)

    assert adapter.phases == [
        ("C123", "1000.1", ProcessingPhase.THINKING, "T123"),
        ("C123", "1000.1", ProcessingPhase.USING_TOOL, "T123"),
    ]
