import pytest
from pydantic_ai import ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.function import FunctionModel, AgentInfo
from pydantic_ai import ModelResponse as MR, TextPart as TP

from easyagents.context.manager import ContextManager
from easyagents.core.exceptions import ContextCompressionError


def make_messages(count: int) -> list:
    """Generate a list of ModelMessage objects."""
    messages = []
    for i in range(count):
        messages.append(ModelRequest(parts=[UserPromptPart(content=f"Message {i}" * 100)]))
        messages.append(ModelResponse(parts=[TextPart(content=f"Response {i}" * 100)]))
    return messages


def make_summarizing_handler(summary: str = "Summary of conversation"):
    """Create a FunctionModel that returns a summary."""
    def handler(messages, info: AgentInfo) -> MR:
        return MR(parts=[TP(content=summary)])
    return FunctionModel(handler)


@pytest.mark.asyncio
async def test_no_compression_below_threshold():
    """Messages below threshold are returned unchanged."""
    ctx = ContextManager(model="test", max_tokens=999999)
    messages = make_messages(2)
    result = await ctx.compress_if_needed(messages)
    assert result is messages  # Same object, no compression


@pytest.mark.asyncio
async def test_compression_triggered_above_threshold():
    """Messages above threshold are compressed."""
    ctx = ContextManager(model="test", max_tokens=100, keep_recent=2)
    messages = make_messages(10)  # 20 messages, well above threshold

    result = await ctx.compress_if_needed(
        messages, model=make_summarizing_handler("Compressed summary")
    )

    # Result should be: [summary_message] + keep_recent messages
    assert len(result) == 3  # 1 summary + 2 recent


@pytest.mark.asyncio
async def test_keep_recent_preserved():
    """Recent messages are preserved in compression output."""
    ctx = ContextManager(model="test", max_tokens=100, keep_recent=4)
    messages = make_messages(10)  # 20 messages

    result = await ctx.compress_if_needed(
        messages, model=make_summarizing_handler("Summary")
    )

    # Last 4 messages should be preserved
    assert len(result) == 5  # 1 summary + 4 recent
    # The last 4 messages should match the last 4 of the original
    assert result[-4:] == messages[-4:]


@pytest.mark.asyncio
async def test_compression_failure_raises_error():
    """LLM failure during compression raises ContextCompressionError."""
    def failing_handler(messages, info: AgentInfo) -> MR:
        raise RuntimeError("LLM unavailable")

    ctx = ContextManager(model="test", max_tokens=100, keep_recent=2)
    messages = make_messages(10)

    with pytest.raises(ContextCompressionError):
        await ctx.compress_if_needed(messages, model=FunctionModel(failing_handler))
