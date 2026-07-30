from dataclasses import dataclass, field
from typing import Any

from pydantic_ai import Agent

from easyagents.core.exceptions import (
    AgentAlreadyRegisteredError,
    AgentNotFoundError,
)
from easyagents.tools.registry import ToolRegistry


@dataclass
class AgentDefinition:
    name: str
    instructions: str
    model: str
    tools: list[str] = field(default_factory=list)
    output_type: type | None = None
    deps_type: type | None = None
    description: str = ""
    subagents: list[str] = field(default_factory=list)


class AgentRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, AgentDefinition] = {}
        self._agents: dict[str, Agent[Any]] = {}

    def register(self, definition: AgentDefinition) -> None:
        if definition.name in self._definitions:
            raise AgentAlreadyRegisteredError(
                f"Agent '{definition.name}' is already registered"
            )
        self._definitions[definition.name] = definition

    def get(self, name: str) -> AgentDefinition:
        if name not in self._definitions:
            raise AgentNotFoundError(f"Agent '{name}' is not registered")
        return self._definitions[name]

    def create(self, name: str, tool_registry: ToolRegistry) -> Agent[Any]:
        if name in self._agents:
            return self._agents[name]

        definition = self.get(name)
        pydantic_tools = tool_registry.resolve(definition.tools)

        if definition.subagents:
            from easyagents.patterns.delegation import DelegationManager

            dm = DelegationManager(
                parent_name=name,
                subagent_names=definition.subagents,
                registry=self,
                tool_registry=tool_registry,
            )
            pydantic_tools.extend(dm.create_delegation_tools())

        kwargs: dict[str, Any] = {
            "model": definition.model,
            "name": definition.name,
            "system_prompt": definition.instructions,
            "tools": pydantic_tools,
        }
        if definition.output_type is not None:
            kwargs["output_type"] = definition.output_type

        agent: Agent[Any] = Agent(**kwargs)
        self._agents[name] = agent
        return agent

    def list(self) -> list[str]:
        return list(self._definitions.keys())
