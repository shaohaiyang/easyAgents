class EasyAgentsError(Exception):
    """Base exception for all EasyAgents errors."""


class AgentAlreadyRegisteredError(EasyAgentsError):
    """Raised when registering an agent with a name that already exists."""


class AgentNotFoundError(EasyAgentsError):
    """Raised when looking up an agent that doesn't exist in the registry."""


class ToolAlreadyRegisteredError(EasyAgentsError):
    """Raised when registering a tool with a name that already exists."""


class ToolNotFoundError(EasyAgentsError):
    """Raised when resolving a tool name that doesn't exist in the registry."""


class DelegationError(EasyAgentsError):
    """Raised when a delegation call fails (subagent crashes, returns invalid output)."""


class SessionStoreError(EasyAgentsError):
    """Raised when a session store backend operation fails."""


class ContextCompressionError(EasyAgentsError):
    """Raised when context compression fails (LLM error, serialization error)."""


class OrchestrationError(EasyAgentsError):
    """Raised when orchestrator-worker execution fails."""


class HandoffError(EasyAgentsError):
    """Raised when a handoff between agents fails."""


class RoutingError(EasyAgentsError):
    """Raised when agent routing fails (no match, LLM error)."""


class WorkflowError(EasyAgentsError):
    """Raised when a graph workflow execution fails."""


class CheckpointError(EasyAgentsError):
    """Raised when checkpoint save/load/rollback fails."""


class ApprovalError(EasyAgentsError):
    """Raised when approval resumption fails (invalid state, already resumed)."""
