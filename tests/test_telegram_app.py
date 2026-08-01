import pytest

from msclaw.telegram_app import split_message


def test_split_message_respects_limit() -> None:
    assert split_message("abcdefgh", limit=3) == ["abc", "def", "gh"]


def test_split_message_handles_empty_text() -> None:
    assert split_message("") == [""]


def test_split_message_rejects_invalid_limit() -> None:
    with pytest.raises(ValueError):
        split_message("text", limit=0)
