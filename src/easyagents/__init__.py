"""EasyAgents - Multi-agent workbench built on Pydantic AI."""

from easyagents.core.agent import AgentDefinition, AgentRegistry
from easyagents.core.session import Session, SessionManager
from easyagents.core.exceptions import (
    EasyAgentsError,
    AgentAlreadyRegisteredError,
    AgentNotFoundError,
    ToolAlreadyRegisteredError,
    ToolNotFoundError,
    DelegationError,
)
from easyagents.tools.registry import ToolRegistry, ToolMetadata
from easyagents.tools.builtin.web_search import web_search
from easyagents.observability.tracing import configure

__all__ = [
    "AgentDefinition",
    "AgentRegistry",
    "Session",
    "SessionManager",
    "ToolRegistry",
    "ToolMetadata",
    "web_search",
    "configure",
    "EasyAgentsError",
    "AgentAlreadyRegisteredError",
    "AgentNotFoundError",
    "ToolAlreadyRegisteredError",
    "ToolNotFoundError",
    "DelegationError",
]
