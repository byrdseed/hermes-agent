from types import SimpleNamespace

from gateway.run import _inject_auto_context_for_new_session


def test_auto_context_is_injected_on_first_session_turn():
    event = SimpleNamespace(text="Handle this", auto_context="[Channel context]\nMinimal facts")

    _inject_auto_context_for_new_session(event, is_new_session=True)

    assert event.text == "[Channel context]\nMinimal facts\n\nHandle this"


def test_auto_context_does_not_change_ongoing_session_turn():
    event = SimpleNamespace(text="Continue", auto_context="[Channel context]\nChanged facts")

    _inject_auto_context_for_new_session(event, is_new_session=False)

    assert event.text == "Continue"
