from typing import Any

from pydantic_ai import Agent

from easyagents.core.exceptions import RoutingError


class RouterPattern:
    """Routes user input to the best agent using LLM intent classification."""

    def __init__(
        self,
        agents: list[str],
        registry: Any,
        tool_registry: Any,
        model: str = "openai:gpt-4o",
        routing_prompt: str = "",
    ) -> None:
        if not agents:
            raise ValueError("agents list cannot be empty")

        self.agents = agents
        self.registry = registry
        self.tool_registry = tool_registry
        self.model = model
        self.routing_prompt = routing_prompt

    async def route(
        self,
        user_input: str,
        model: Any = None,
    ) -> str:
        """Analyze user input and return the best agent name."""
        system_prompt = self.routing_prompt or self._build_routing_prompt()

        router_agent = Agent(model=self.model, system_prompt=system_prompt)

        run_kwargs: dict[str, Any] = {}
        if model is not None:
            run_kwargs["model"] = model

        result = await router_agent.run(user_input, **run_kwargs)
        agent_name = str(result.output).strip()

        if agent_name not in self.agents:
            raise RoutingError(
                f"Router returned unknown agent '{agent_name}'. "
                f"Valid agents: {self.agents}"
            )

        return agent_name

    async def run(
        self,
        user_input: str,
        model: Any = None,
    ) -> Any:
        """Route + execute: route first, then run the selected agent."""
        agent_name = await self.route(user_input, model=model)

        agent = self.registry.create(agent_name, self.tool_registry)
        run_kwargs: dict[str, Any] = {}
        if model is not None:
            run_kwargs["model"] = model
        result = await agent.run(user_input, **run_kwargs)
        return result.output

    def _build_routing_prompt(self) -> str:
        """Auto-generate routing prompt from agent descriptions."""
        lines = [
            "You are a router. Given the user input, select the best agent.",
            "Available agents:",
        ]
        for name in self.agents:
            try:
                definition = self.registry.get(name)
                desc = definition.description or name
            except Exception:
                desc = name
            lines.append(f"- {name}: {desc}")
        lines.append("Respond with ONLY the agent name, nothing else.")
        return "\n".join(lines)
