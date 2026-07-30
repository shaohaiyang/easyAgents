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
