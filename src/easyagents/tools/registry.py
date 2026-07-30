import inspect
from typing import Any, Callable

from pydantic_ai import Tool

from easyagents.core.exceptions import (
    ToolAlreadyRegisteredError,
    ToolNotFoundError,
)
from easyagents.tools.base import ToolMetadata


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}
        self._descriptions: dict[str, str] = {}

    def register(
        self, name: str, func: Callable[..., Any], description: str = ""
    ) -> None:
        if name in self._tools:
            raise ToolAlreadyRegisteredError(
                f"Tool '{name}' is already registered"
            )
        self._tools[name] = func
        self._descriptions[name] = description

    def resolve(self, names: list[str]) -> list[Tool]:
        tools: list[Tool] = []
        for name in names:
            if name not in self._tools:
                raise ToolNotFoundError(
                    f"Tool '{name}' is not registered"
                )
            tools.append(Tool(self._tools[name]))
        return tools

    def get(self, name: str) -> ToolMetadata:
        if name not in self._tools:
            raise ToolNotFoundError(
                f"Tool '{name}' is not registered"
            )
        func = self._tools[name]
        sig = inspect.signature(func)
        params = {
            p.name: {"kind": p.kind.name, "annotation": str(p.annotation)}
            for p in sig.parameters.values()
            if p.name != "ctx"
        }
        desc = self._descriptions.get(name) or func.__doc__ or ""
        return ToolMetadata(name=name, description=desc, parameters=params)

    def list(self) -> list[ToolMetadata]:
        return [self.get(name) for name in self._tools]
