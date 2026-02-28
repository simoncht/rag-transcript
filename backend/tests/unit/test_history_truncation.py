"""
Tests for conversation history truncation — old assistant messages are truncated
to reduce token usage in LLM prompts.
"""
from types import SimpleNamespace

import pytest

from app.api.utils import truncate_history_messages as _truncate_history_messages


def _msg(role: str, content: str):
    """Create a simple message-like object."""
    return SimpleNamespace(role=role, content=content)


class TestHistoryTruncation:
    def test_old_assistant_messages_truncated(self):
        """Old assistant messages beyond truncate_chars should be truncated."""
        messages = [
            _msg("user", "Hello"),
            _msg("assistant", "A" * 500),  # old assistant — should be truncated
            _msg("user", "Tell me more"),
            _msg("assistant", "B" * 500),  # most recent assistant — kept in full
            _msg("user", "Thanks"),
        ]
        result = _truncate_history_messages(messages, truncate_chars=300)

        # Old assistant (index 1) should be truncated: content[:300] + "..." = 303 chars
        assert result[1][0] == "assistant"
        assert len(result[1][1]) == 303
        assert result[1][1].endswith("...")

        # Most recent assistant (index 3) should be kept in full
        assert result[3][0] == "assistant"
        assert result[3][1] == "B" * 500

    def test_last_assistant_message_kept_full(self):
        """The most recent assistant response should never be truncated."""
        messages = [
            _msg("user", "Question"),
            _msg("assistant", "C" * 1000),  # only assistant — should be kept
        ]
        result = _truncate_history_messages(messages, truncate_chars=300)
        assert result[1][1] == "C" * 1000

    def test_user_messages_never_truncated(self):
        """User messages should always be kept in full regardless of length."""
        messages = [
            _msg("user", "X" * 1000),
            _msg("assistant", "Short reply"),
            _msg("user", "Y" * 800),
        ]
        result = _truncate_history_messages(messages, truncate_chars=300)
        assert result[0][1] == "X" * 1000
        assert result[2][1] == "Y" * 800

    def test_short_assistant_messages_unchanged(self):
        """Assistant messages under truncate_chars should not be modified."""
        messages = [
            _msg("user", "Hi"),
            _msg("assistant", "Hello there!"),  # 12 chars < 300
            _msg("user", "Question"),
            _msg("assistant", "Answer"),
        ]
        result = _truncate_history_messages(messages, truncate_chars=300)
        assert result[1][1] == "Hello there!"
        assert result[3][1] == "Answer"

    def test_truncation_disabled_when_zero(self):
        """When truncate_chars=0, no truncation should occur."""
        messages = [
            _msg("user", "Hi"),
            _msg("assistant", "D" * 500),
            _msg("user", "More"),
            _msg("assistant", "E" * 500),
        ]
        result = _truncate_history_messages(messages, truncate_chars=0)
        assert result[1][1] == "D" * 500
        assert result[3][1] == "E" * 500

    def test_empty_messages(self):
        """Empty message list should return empty list."""
        result = _truncate_history_messages([], truncate_chars=300)
        assert result == []

    def test_single_user_message(self):
        """Single user message should pass through unchanged."""
        messages = [_msg("user", "Hello")]
        result = _truncate_history_messages(messages, truncate_chars=300)
        assert result == [("user", "Hello")]

    def test_multiple_old_assistants_all_truncated(self):
        """All old assistant messages (except last) should be truncated."""
        messages = [
            _msg("user", "Q1"),
            _msg("assistant", "F" * 600),  # old — truncated
            _msg("user", "Q2"),
            _msg("assistant", "G" * 600),  # old — truncated
            _msg("user", "Q3"),
            _msg("assistant", "H" * 600),  # most recent — kept
        ]
        result = _truncate_history_messages(messages, truncate_chars=300)

        assert len(result[1][1]) == 303  # truncated
        assert result[1][1].endswith("...")
        assert len(result[3][1]) == 303  # truncated
        assert result[3][1].endswith("...")
        assert result[5][1] == "H" * 600  # kept in full
