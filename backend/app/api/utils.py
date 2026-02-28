"""Shared utilities for API route handlers."""


def format_timestamp_display(start: float, end: float) -> str:
    """Format seconds into MM:SS or HH:MM:SS range."""
    start_h, start_rem = divmod(int(start), 3600)
    start_m, start_s = divmod(start_rem, 60)
    end_h, end_rem = divmod(int(end), 3600)
    end_m, end_s = divmod(end_rem, 60)

    if start_h or end_h:
        return f"{start_h:02d}:{start_m:02d}:{start_s:02d} - {end_h:02d}:{end_m:02d}:{end_s:02d}"
    return f"{start_m:02d}:{start_s:02d} - {end_m:02d}:{end_s:02d}"


def _unpack(msg):
    """Extract (role, content) from either an ORM object or a tuple."""
    if isinstance(msg, tuple):
        return msg[0], msg[1]
    return msg.role, msg.content


def truncate_history_messages(messages, truncate_chars=300):
    """
    Truncate old assistant messages to save tokens in LLM prompt.

    Keeps the most recent assistant message in full, truncates older ones.
    User messages are never truncated.

    Args:
        messages: List of message objects (.role/.content) or (role, content) tuples
        truncate_chars: Max chars for old assistant messages (0=disabled)

    Returns:
        List of (role, content) tuples with truncation applied
    """
    if not messages or truncate_chars <= 0:
        return [_unpack(msg) for msg in messages]

    result = []
    # Find the index of the last assistant message
    last_assistant_idx = -1
    for i in range(len(messages) - 1, -1, -1):
        role, _ = _unpack(messages[i])
        if role == "assistant":
            last_assistant_idx = i
            break

    for i, msg in enumerate(messages):
        role, content = _unpack(msg)
        if (
            role == "assistant"
            and i != last_assistant_idx
            and len(content) > truncate_chars
        ):
            content = content[:truncate_chars] + "..."
        result.append((role, content))

    return result
