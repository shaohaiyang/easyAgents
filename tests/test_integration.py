import pytest
from pydantic import BaseModel
from pydantic_ai.models.function import FunctionModel, AgentInfo
from pydantic_ai import ModelResponse, TextPart

from easyagents import (
    AgentDefinition,
    AgentRegistry,
    ToolRegistry,
    web_search,
)


class ResearchFindings(BaseModel):
    products: list[str]
    summary: str


@pytest.fixture
def handler():
    def handle(messages: list, info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(
            content='{"products": ["AirPods Pro 2", "Sony WF-1000XM5", "Bose QC Ultra"], "summary": "Three top competitors in the high-end TWS market."}'
        )])
    return FunctionModel(handle)


@pytest.mark.asyncio
async def test_bluetooth_earphone_research(handler):
    """End-to-end test: orchestrator delegates to researcher via delegation."""

    tools = ToolRegistry()
    tools.register("web_search", web_search)

    agents = AgentRegistry()

    agents.register(AgentDefinition(
        name="researcher",
        instructions="You are a product researcher. Use web_search to research.",
        model="test",
        tools=["web_search"],
        output_type=ResearchFindings,
        description="Product researcher",
    ))

    agents.register(AgentDefinition(
        name="orchestrator",
        instructions="You are a research orchestrator. Use delegate_researcher to delegate.",
        model="test",
        subagents=["researcher"],
        description="Research orchestrator",
    ))

    agent = agents.create("orchestrator", tools)
    result = await agent.run(
        "调研最近爆火的蓝牙耳机",
        model=handler,
    )
    assert result.output is not None


def test_full_pipeline():
    """Simplified pipeline test: register, create, and run with TestModel."""
    from pydantic_ai.models.test import TestModel

    tools = ToolRegistry()
    tools.register("web_search", lambda q: [{"title": "X", "url": "https://x.com", "snippet": "test"}])

    agents = AgentRegistry()
    agents.register(AgentDefinition(
        name="researcher",
        instructions="Research.",
        model="test",
        tools=["web_search"],
        output_type=ResearchFindings,
    ))
    agents.register(AgentDefinition(
        name="orchestrator",
        instructions="Delegate.",
        model="test",
        subagents=["researcher"],
    ))

    agent = agents.create("orchestrator", tools)
    result = agent.run_sync("research bluetooth earphones", model=TestModel())
    assert result.output is not None
    assert len(result.all_messages()) > 0
