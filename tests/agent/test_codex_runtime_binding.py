from types import SimpleNamespace

from agent.codex_runtime import (
    CodexRuntimeBinding,
    _projected_messages_for_persistence,
)


class _Client:
    def __init__(self, thread_id=None):
        self.thread_id = thread_id
        self.closed = False
        self.interrupts = 0
        self.steers = []

    def close(self):
        self.closed = True

    def request_interrupt(self):
        self.interrupts += 1

    def request_steer(self, text):
        self.steers.append(text)
        return True


def test_logical_session_switch_retires_client_and_thread_together():
    client = _Client("thread-a")
    binding = CodexRuntimeBinding(
        client=client,
        owner_session_id="session-a",
        thread_id="thread-a",
    )

    binding.bind("session-b")

    assert client.closed is True
    assert binding.client is None
    assert binding.owner_session_id == "session-b"
    assert binding.thread_id is None


def test_retirement_preserves_live_client_thread_for_replacement():
    client = _Client("thread-current")
    binding = CodexRuntimeBinding(client=client, owner_session_id="session-a")

    binding.retire(preserve_thread=True)

    assert client.closed is True
    assert binding.client is None
    assert binding.resume_thread_id("session-a") == "thread-current"


def test_stale_turn_cannot_overwrite_new_session_binding():
    binding = CodexRuntimeBinding(
        owner_session_id="session-new",
        thread_id="thread-new",
    )

    recorded = binding.record_thread(
        session_id="session-old",
        thread_id="thread-old",
    )

    assert recorded is False
    assert binding.owner_session_id == "session-new"
    assert binding.thread_id == "thread-new"


def test_client_factory_gets_durable_thread_and_controls_live_requests():
    created_with = []

    def factory(resume_thread_id):
        created_with.append(resume_thread_id)
        return _Client(resume_thread_id)

    binding = CodexRuntimeBinding()
    client = binding.ensure_client(
        session_id="session-a",
        factory=factory,
        durable_thread_id="thread-from-db",
    )

    binding.request_interrupt()
    assert binding.request_steer("change course") is True
    assert created_with == ["thread-from-db"]
    assert client.interrupts == 1
    assert client.steers == ["change course"]


def test_unseen_partial_final_is_not_persisted():
    turn = SimpleNamespace(
        error="timed out",
        final_text="I'm continuing.",
        projected_messages=[
            {"role": "assistant", "content": "Visible setup"},
            {"role": "tool", "content": "partial result", "tool_call_id": "call-1"},
            {"role": "assistant", "content": "I'm continuing."},
        ],
    )

    projected = _projected_messages_for_persistence(turn, response_previewed=False)

    assert projected == [
        {"role": "assistant", "content": "Visible setup"},
        {"role": "tool", "content": "partial result", "tool_call_id": "call-1"},
    ]