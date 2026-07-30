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
    SessionStoreError,
    ContextCompressionError,
)
from easyagents.tools.registry import ToolRegistry, ToolMetadata
from easyagents.tools.builtin.web_search import web_search
from easyagents.tools.builtin.http_request import http_request
from easyagents.tools.builtin.write_file import write_file
from easyagents.observability.tracing import configure
from easyagents.persistence.base import SessionStore
from easyagents.persistence.memory import InMemorySessionStore
from easyagents.persistence.sqlite import SQLiteSessionStore
from easyagents.context.manager import ContextManager

__all__ = [
    # MVP (existing)
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
    # Phase 1.5 (new)
    "SessionStore",
    "InMemorySessionStore",
    "SQLiteSessionStore",
    "ContextManager",
    "http_request",
    "write_file",
    "SessionStoreError",
    "ContextCompressionError",
]
