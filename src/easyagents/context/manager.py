from typing import Any

from pydantic_ai import Agent, ModelMessage, ModelRequest
from pydantic_ai.messages import SystemPromptPart

from easyagents.core.exceptions import ContextCompressionError


_DEFAULT_PROMPT = (
    "Summarize the following conversation concisely, preserving key facts, "
    "decisions, and context. Return only the summary text."
)


class ContextManager:
    """Manages conversation context by compressing messages when token count exceeds a threshold.

    Uses an LLM to summarize old messages while preserving recent ones.
    """

    def __init__(
        self,
        model: str = "openai:gpt-4o",
        max_tokens: int = 8000,
        keep_recent: int = 4,
        compression_prompt: str = "",
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self.keep_recent = keep_recent
        self.compression_prompt = compression_prompt or _DEFAULT_PROMPT

    async def compress_if_needed(
        self, messages: list[ModelMessage], model: Any = None
    ) -> list[ModelMessage]:
        """Check token count, compress if threshold exceeded.

        Args:
            messages: The full message history.
            model: Optional model override for testing (FunctionModel/TestModel).

        Returns:
            Original messages if below threshold, or [summary_message] + recent_messages if above.
        """
        token_count = self._count_tokens(messages)
        if token_count <= self.max_tokens:
            return messages

        return await self._compress(messages, model, token_count)

    async def _compress(
        self,
        messages: list[ModelMessage],
        model: Any = None,
        token_count: int = 0,
    ) -> list[ModelMessage]:
        """Summarize old messages, keep recent ones."""
        if len(messages) <= self.keep_recent:
            return messages

        old_messages = messages[:-self.keep_recent]
        recent_messages = messages[-self.keep_recent:]

        conversation_text = self._format_messages(old_messages)

        try:
            agent = Agent(model=self.model, system_prompt=self.compression_prompt)
            run_kwargs: dict[str, Any] = {}
            if model is not None:
                run_kwargs["model"] = model
            result = await agent.run(conversation_text, **run_kwargs)
            summary = result.output if isinstance(result.output, str) else str(result.output)
        except ContextCompressionError:
            raise
        except Exception as e:
            raise ContextCompressionError(
                f"Context compression failed: {e} "
                f"(messages={len(messages)}, tokens={token_count})"
            ) from e

        summary_message = ModelRequest(
            parts=[SystemPromptPart(content=f"Previous conversation summary: {summary}")]
        )

        return [summary_message] + recent_messages

    def _count_tokens(self, messages: list[ModelMessage]) -> int:
        """Estimate token count using a simple heuristic.

        Uses len(str(messages)) // 4 as a rough approximation.
        Conservative (tends to overcount), which is safe for threshold checking.
        """
        return len(str(messages)) // 4

    def _format_messages(self, messages: list[ModelMessage]) -> str:
        """Convert messages to a text format for summarization."""
        lines = []
        for msg in messages:
            for part in msg.parts:
                content = getattr(part, "content", str(part))
                if content:
                    lines.append(str(content))
        return "\n".join(lines)
