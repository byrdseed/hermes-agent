"""Codex runtime invalidation for TUI transcript rewrites."""

from threading import RLock
from unittest.mock import MagicMock

from tui_gateway.server import _rewind_active_session_history


def test_tui_rewind_invalidates_live_codex_thread():
    agent = MagicMock()
    session = {
        "history": [
            {"role": "user", "content": "rewrite me"},
            {"role": "assistant", "content": "old answer"},
        ],
        "history_lock": RLock(),
        "agent": agent,
        "history_version": 0,
    }

    installed, live_view, rewound_count = _rewind_active_session_history(session, 0)

    assert installed == []
    assert live_view["content"] == "rewrite me"
    assert rewound_count == 2
    agent._invalidate_codex_runtime_thread.assert_called_once_with()