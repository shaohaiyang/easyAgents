from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic_ai import RunUsage
from pydantic_graph import BaseNode, GraphRunContext, End

from easyagents.core.exceptions import WorkflowError


@dataclass
class PendingApproval:
    """Returned when graph pauses for approval."""
    prompt: str
    state: Any
    resume_node: Any


@dataclass
class ApprovalResult:
    """User's approval response."""
    approved: bool
    feedback: str = ""


@dataclass
class GraphResult:
    """Final result of graph execution."""
    output: Any
    usage: RunUsage = field(default_factory=RunUsage)
    checkpoints: list[str] = field(default_factory=list)


class GraphWorkflow:
    """Executes a graph of nodes with optional HITL and checkpointing."""

    def __init__(
        self,
        registry: Any = None,
        tool_registry: Any = None,
        checkpoint_manager: Any = None,
    ) -> None:
        self.registry = registry
        self.tool_registry = tool_registry
        self.checkpoint_manager = checkpoint_manager

    async def run(
        self,
        start_node: BaseNode,
        state: Any,
        model: Any = None,
    ) -> GraphResult | PendingApproval:
        """Execute graph from start_node. Returns PendingApproval if paused."""
        ctx = GraphRunContext(state=state, deps=None)
        node = start_node

        while True:
            try:
                result = await node.run(ctx)
            except (WorkflowError,):
                raise
            except Exception as e:
                raise WorkflowError(
                    f"Node {type(node).__name__} failed: {e}"
                ) from e

            if isinstance(result, End):
                data = result.data
                if isinstance(data, PendingApproval):
                    return data
                return GraphResult(output=data)

            node = result

    async def resume(
        self,
        pending: PendingApproval,
        approval: ApprovalResult,
        model: Any = None,
    ) -> GraphResult | PendingApproval:
        """Resume graph after approval."""
        if not approval.approved:
            return GraphResult(
                output=f"Rejected: {approval.feedback}" if approval.feedback else "Rejected",
            )

        return await self.run(pending.resume_node, pending.state, model=model)
