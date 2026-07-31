import asyncio
from dataclasses import dataclass
from typing import Any

from pydantic_ai import RunUsage

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
