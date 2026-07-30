from typing import Any, Optional

from pydantic_ai import RunUsage, Tool

from easyagents.core.exceptions import DelegationError


class DelegationManager:
    def __init__(
        self,
        parent_name: str,
        subagent_names: list[str],
        registry: Any,
        tool_registry: Any,
    ) -> None:
        self.parent_name = parent_name
        self.subagent_names = subagent_names
        self.registry = registry
        self.tool_registry = tool_registry

    def create_delegation_tools(self) -> list[Tool]:
        tools: list[Tool] = []
        for name in self.subagent_names:
            delegate_func = self._make_delegate_func(name)
            tools.append(Tool(delegate_func))
        return tools

    def _make_delegate_func(self, subagent_name: str):
        from pydantic_ai import RunContext

        async def delegate(ctx: RunContext[None], task: str) -> Any:
            try:
                subagent = self.registry.create(subagent_name, self.tool_registry)
                result = await subagent.run(task, usage=ctx.usage)
                return result.output
            except Exception as e:
                raise DelegationError(
                    f"Delegation to '{subagent_name}' failed: {e}"
                ) from e

        delegate.__name__ = f"delegate_{subagent_name}"
        return delegate

    async def delegate(
        self,
        subagent_name: str,
        task: str,
        parent_usage: RunUsage,
        model: Optional[Any] = None,
    ) -> Any:
        try:
            subagent = self.registry.create(subagent_name, self.tool_registry)
            kwargs = {"usage": parent_usage}
            if model is not None:
                kwargs["model"] = model
            result = await subagent.run(task, **kwargs)
            return result.output
        except Exception as e:
            raise DelegationError(
                f"Delegation to '{subagent_name}' failed: {e}"
            ) from e
