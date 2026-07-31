from dataclasses import dataclass
from typing import Any

from pydantic_ai import RunUsage

from easyagents.core.exceptions import HandoffError


@dataclass
class HandoffResult:
    """Result of handoff chain execution."""
    output: Any
    agent_chain: list[str]
    total_messages: int
    usage: RunUsage


class HandoffPattern:
    """Executes a chain of agents sequentially, transferring conversation history."""

    def __init__(
        self,
        agents: list[str],
        registry: Any,
        tool_registry: Any,
        context_mode: str = "full",
        context_manager: Any = None,
        task_templates: list[str] | None = None,
    ) -> None:
        if not agents:
            raise ValueError("agents list cannot be empty")
        if task_templates is not None and len(task_templates) != len(agents):
            raise ValueError(
                f"task_templates length ({len(task_templates)}) must match agents length ({len(agents)})"
            )

        self.agents = agents
        self.registry = registry
        self.tool_registry = tool_registry
        self.context_mode = context_mode
        self.context_manager = context_manager
        self.task_templates = task_templates

    async def run(
        self,
        user_input: str,
        model: Any = None,
    ) -> HandoffResult:
        usage = RunUsage()
        history: list = []
        total_messages = 0
        output: Any = None

        for i, agent_name in enumerate(self.agents):
            if i == 0:
                task = user_input
                if self.task_templates:
                    task = self.task_templates[0].format(input=user_input)
                run_kwargs: dict[str, Any] = {"usage": usage}
                if model is not None:
                    run_kwargs["model"] = model
                if history:
                    run_kwargs["message_history"] = history
                result = await self._run_agent(agent_name, task, **run_kwargs)
            else:
                task = (
                    self.task_templates[i]
                    if self.task_templates
                    else "Continue based on the previous conversation."
                )
                run_kwargs = {"usage": usage}
                if model is not None:
                    run_kwargs["model"] = model
                if history:
                    run_kwargs["message_history"] = history
                result = await self._run_agent(agent_name, task, **run_kwargs)

            output = result.output
            messages = result.all_messages()
            total_messages += len(messages)

            history = await self._process_context(messages, model)

        return HandoffResult(
            output=output,
            agent_chain=list(self.agents),
            total_messages=total_messages,
            usage=usage,
        )

    async def _run_agent(self, agent_name: str, task: str, **kwargs) -> Any:
        try:
            agent = self.registry.create(agent_name, self.tool_registry)
            result = await agent.run(task, **kwargs)
            return result
        except Exception as e:
            raise HandoffError(
                f"Agent '{agent_name}' failed during handoff: {e}"
            ) from e

    async def _process_context(self, messages: list, model: Any = None) -> list:
        if self.context_mode == "none":
            return []
        if self.context_mode == "compressed":
            if self.context_manager is None:
                raise HandoffError(
                    "context_mode='compressed' requires a context_manager"
                )
            return await self.context_manager.compress_if_needed(messages, model=model)
        return messages
