import asyncio
import json
from dataclasses import dataclass
from typing import Any

from pydantic_ai import Agent, RunUsage

from easyagents.core.exceptions import OrchestrationError


@dataclass
class SubtaskTemplate:
    """A predefined subtask for parallel execution."""
    agent: str
    task_template: str
    description: str = ""


@dataclass
class OrchestrationResult:
    """Result of orchestrator-worker execution."""
    output: Any
    subtask_results: list[Any]
    usage: RunUsage


class OrchestratorWorker:
    """Executes predefined subtask templates in parallel across multiple subagents.

    Note: ``orchestrator_agent`` is currently reserved for future use. It will drive
    LLM-driven decomposition in Phase 3, but is retained here as part of the public
    API so callers can wire it up ahead of time.
    """

    def __init__(
        self,
        orchestrator_agent: str,
        subtasks: list[SubtaskTemplate],
        registry: Any,
        tool_registry: Any,
        synthesis_agent: str | None = None,
        context_manager: Any = None,
    ) -> None:
        self.orchestrator_agent = orchestrator_agent
        self.subtasks = subtasks
        self.registry = registry
        self.tool_registry = tool_registry
        self.synthesis_agent = synthesis_agent
        self.context_manager = context_manager

    async def run(
        self,
        user_input: str,
        params: dict[str, str] | None = None,
        model: Any = None,
    ) -> OrchestrationResult:
        params = params or {}

        filled_tasks = []
        for subtask in self.subtasks:
            try:
                task = subtask.task_template.format(**params)
            except KeyError as e:
                raise OrchestrationError(
                    f"Missing parameter {e} for subtask '{subtask.agent}'"
                ) from e
            filled_tasks.append((subtask.agent, task))

        usage = RunUsage()

        results = await asyncio.gather(
            *[self._run_subtask(name, task, usage, model) for name, task in filled_tasks],
            return_exceptions=True,
        )

        subtask_results: list[Any] = []
        failures: list[str] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                subtask_results.append(None)
                failures.append(f"{filled_tasks[i][0]}: {result}")
            else:
                subtask_results.append(result)

        if all(r is None for r in subtask_results):
            raise OrchestrationError(
                f"All subtasks failed: {'; '.join(failures)}"
            )

        if self.synthesis_agent:
            if self.context_manager:
                from pydantic_ai import ModelRequest, ModelResponse, TextPart, UserPromptPart

                # Build pseudo-messages from subtask results for compression
                pseudo_messages = []
                for r in subtask_results:
                    if r is not None:
                        pseudo_messages.append(
                            ModelRequest(parts=[UserPromptPart(content=str(r))])
                        )
                        pseudo_messages.append(
                            ModelResponse(parts=[TextPart(content=str(r))])
                        )
                if pseudo_messages:
                    compressed = await self.context_manager.compress_if_needed(
                        pseudo_messages, model=model
                    )
                    # Extract text from compressed messages
                    valid_results = [
                        str(getattr(p, "content", ""))
                        for msg in compressed
                        for p in msg.parts
                    ]
                    synthesis_input = "\n".join(valid_results)
                else:
                    synthesis_input = ""
            else:
                valid_results = [str(r) for r in subtask_results if r is not None]
                synthesis_input = "\n".join(valid_results)
            try:
                agent = self.registry.create(self.synthesis_agent, self.tool_registry)
                run_kwargs: dict[str, Any] = {"usage": usage}
                if model is not None:
                    run_kwargs["model"] = model
                result = await agent.run(
                    f"Synthesize the following results:\n{synthesis_input}",
                    **run_kwargs,
                )
                output = result.output
            except Exception:
                output = "\n".join(str(r) for r in subtask_results if r is not None)
        else:
            output = "\n".join(str(r) for r in subtask_results if r is not None)

        return OrchestrationResult(
            output=output,
            subtask_results=subtask_results,
            usage=usage,
        )

    async def _run_subtask(
        self,
        agent_name: str,
        task: str,
        usage: RunUsage,
        model: Any = None,
    ) -> Any:
        agent = self.registry.create(agent_name, self.tool_registry)
        run_kwargs: dict[str, Any] = {"usage": usage}
        if model is not None:
            run_kwargs["model"] = model
        result = await agent.run(task, **run_kwargs)
        return result.output


@dataclass
class DynamicSubtask:
    """LLM-generated subtask."""
    agent: str
    task: str
    rationale: str


class DynamicOrchestrator:
    """Decomposes tasks dynamically using LLM, then executes subtasks."""

    def __init__(
        self,
        agents: list[str],
        registry: Any,
        tool_registry: Any,
        model: str = "openai:gpt-4o",
        decomposition_prompt: str = "",
        synthesis_agent: str | None = None,
        context_manager: Any = None,
    ) -> None:
        self.agents = agents
        self.registry = registry
        self.tool_registry = tool_registry
        self.model = model
        self.decomposition_prompt = decomposition_prompt
        self.synthesis_agent = synthesis_agent
        self.context_manager = context_manager

    async def decompose(self, task: str, model: Any = None) -> list[DynamicSubtask]:
        prompt = self._build_decomposition_prompt()
        agent = Agent(model=self.model, system_prompt=prompt)

        run_kwargs: dict[str, Any] = {}
        if model is not None:
            run_kwargs["model"] = model

        result = await agent.run(task, **run_kwargs)
        raw_output = str(result.output).strip()

        try:
            subtask_data = json.loads(raw_output)
        except json.JSONDecodeError as e:
            raise OrchestrationError(
                f"LLM returned invalid JSON for decomposition: {raw_output[:200]}"
            ) from e

        subtasks = []
        for item in subtask_data:
            subtask = DynamicSubtask(
                agent=item["agent"],
                task=item["task"],
                rationale=item.get("rationale", ""),
            )
            if subtask.agent not in self.agents:
                raise OrchestrationError(
                    f"LLM selected unknown agent '{subtask.agent}'. "
                    f"Valid agents: {self.agents}"
                )
            subtasks.append(subtask)

        return subtasks

    async def run(self, task: str, model: Any = None) -> OrchestrationResult:
        subtasks = await self.decompose(task, model=model)

        templates = [
            SubtaskTemplate(agent=s.agent, task_template=s.task)
            for s in subtasks
        ]

        orch = OrchestratorWorker(
            orchestrator_agent="dynamic",
            subtasks=templates,
            registry=self.registry,
            tool_registry=self.tool_registry,
            synthesis_agent=self.synthesis_agent,
            context_manager=self.context_manager,
        )

        return await orch.run(task, params={}, model=model)

    async def run_sequential(self, task: str, model: Any = None) -> OrchestrationResult:
        subtasks = await self.decompose(task, model=model)
        usage = RunUsage()
        results: list[Any] = []
        prev_output = ""

        for subtask in subtasks:
            agent = self.registry.create(subtask.agent, self.tool_registry)
            task_text = subtask.task
            if prev_output:
                task_text = f"{task_text}\n\nPrevious result: {prev_output}"

            run_kwargs: dict[str, Any] = {"usage": usage}
            if model is not None:
                run_kwargs["model"] = model

            try:
                result = await agent.run(task_text, **run_kwargs)
                results.append(result.output)
                prev_output = str(result.output)
            except Exception:
                results.append(None)

        if all(r is None for r in results):
            raise OrchestrationError("All sequential subtasks failed")

        output = "\n".join(str(r) for r in results if r is not None)
        return OrchestrationResult(output=output, subtask_results=results, usage=usage)

    def _build_decomposition_prompt(self) -> str:
        if self.decomposition_prompt:
            return self.decomposition_prompt

        lines = [
            "You are a task decomposer. Break the task into subtasks.",
            "Available agents:",
        ]
        for name in self.agents:
            try:
                definition = self.registry.get(name)
                desc = definition.description or name
            except Exception:
                desc = name
            lines.append(f"- {name}: {desc}")
        lines.append('Return JSON array: [{"agent": "...", "task": "...", "rationale": "..."}]')
        lines.append("Return ONLY the JSON, no other text.")
        return "\n".join(lines)
