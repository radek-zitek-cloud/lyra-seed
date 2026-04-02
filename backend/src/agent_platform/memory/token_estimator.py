"""Token estimation for context budget management."""

from agent_platform.llm.models import Message

# Rough heuristic: ~4 chars per token for English text.
CHARS_PER_TOKEN = 4
MESSAGE_OVERHEAD_TOKENS = 4  # per-message framing overhead


def estimate_tokens(text: str) -> int:
    """Estimate token count for a text string."""
    return len(text) // CHARS_PER_TOKEN + 1


def estimate_messages_tokens(messages: list[Message]) -> int:
    """Estimate total tokens for a list of messages."""
    total = 0
    for msg in messages:
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        total += estimate_tokens(content) + MESSAGE_OVERHEAD_TOKENS
    return total
