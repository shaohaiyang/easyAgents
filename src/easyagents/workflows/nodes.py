from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic_graph import BaseNode, GraphRunContext, End

StateType = TypeVar("StateType")


class AgentNode(BaseNode[StateType], Generic[StateType]):
    """Base class for graph nodes that execute a registered agent.

    Subclasses must override run() to specify next_node logic.
    """
    agent_name: str
    task: str


class ApprovalNode(BaseNode[StateType], Generic[StateType]):
    """Graph node that pauses execution for human approval.

    Returns PendingApproval via End. The caller resumes with GraphWorkflow.resume().
    """
    prompt: str
    next_node: Any
