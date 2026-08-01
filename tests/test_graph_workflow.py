import pytest
from dataclasses import dataclass
from pydantic import BaseModel
from pydantic_ai import ModelResponse, TextPart, RunUsage
from pydantic_ai.models.function import FunctionModel, AgentInfo
from pydantic_graph import BaseNode, GraphRunContext, End

from easyagents.core.agent import AgentDefinition, AgentRegistry
from easyagents.tools.registry import ToolRegistry
from easyagents.workflows.nodes import AgentNode, ApprovalNode
from easyagents.workflows.graph import (
    GraphWorkflow, GraphResult, PendingApproval, ApprovalResult,
)


class TestState(BaseModel):
    query: str = ""
    results: list[str] = []
    usage: RunUsage = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.usage is None:
            self.usage = RunUsage()


def make_handler(output: str = "Agent result"):
    def handler(messages, info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(content=output)])
    return FunctionModel(handler)


@pytest.fixture
def tool_registry():
    return ToolRegistry()


@pytest.fixture
def registry():
    return AgentRegistry()


@pytest.mark.asyncio
async def test_agent_node_executes_agent(registry, tool_registry):
    """AgentNode runs a registered agent and stores output in state."""
    registry.register(AgentDefinition(
        name="worker", instructions="Work.", model="test",
    ))

    class MyState(TestState):
        pass

    class MyNode(AgentNode[MyState]):
        agent_name: str = "worker"
        task: str = "do work"
        next_node: End = None

        async def run(self, ctx: GraphRunContext[MyState]) -> End:
            agent = registry.create("worker", tool_registry)
            result = await agent.run("do work", model=make_handler("Done"))
            ctx.state.results.append(result.output)
            return End("completed")

    wf = GraphWorkflow(registry=registry, tool_registry=tool_registry)
    result = await wf.run(MyNode(), MyState(query="test"), model=make_handler("Done"))

    assert isinstance(result, GraphResult)
    assert result.output == "completed"


@pytest.mark.asyncio
async def test_graph_pauses_at_approval_node(registry, tool_registry):
    """ApprovalNode causes GraphWorkflow to return PendingApproval."""
    registry.register(AgentDefinition(name="worker", instructions="Work.", model="test"))

    class MyState(TestState):
        pass

    class WorkNode(AgentNode[MyState]):
        agent_name: str = "worker"
        task: str = "work"

        async def run(self, ctx: GraphRunContext[MyState]) -> "ApprovalNode[MyState]":
            agent = registry.create("worker", tool_registry)
            result = await agent.run("work", model=make_handler("Work done"))
            ctx.state.results.append(result.output)
            return ApprovalNode(prompt="Approve?", next_node=End("final"))

    @dataclass
    class ApprovalNode(BaseNode[MyState]):
        prompt: str
        next_node: BaseNode[MyState]

        async def run(self, ctx: GraphRunContext[MyState]) -> End:
            return End(PendingApproval(
                prompt=self.prompt,
                state=ctx.state,
                resume_node=self.next_node,
            ))

    wf = GraphWorkflow(registry=registry, tool_registry=tool_registry)
    result = await wf.run(WorkNode(), MyState(query="test"), model=make_handler("Work done"))

    assert isinstance(result, PendingApproval)
    assert result.prompt == "Approve?"


@pytest.mark.asyncio
async def test_resume_after_approval(registry, tool_registry):
    """resume() continues execution after approval."""
    registry.register(AgentDefinition(name="worker", instructions="Work.", model="test"))

    class MyState(TestState):
        pass

    class FinalNode(BaseNode[MyState]):
        async def run(self, ctx: GraphRunContext[MyState]) -> End:
            return End("final output")

    pending = PendingApproval(
        prompt="Approve?",
        state=MyState(query="test", results=["interim"]),
        resume_node=FinalNode(),
    )

    wf = GraphWorkflow(registry=registry, tool_registry=tool_registry)
    result = await wf.resume(pending, ApprovalResult(approved=True), model=make_handler())

    assert isinstance(result, GraphResult)
    assert result.output == "final output"


@pytest.mark.asyncio
async def test_resume_rejected_returns_feedback(registry, tool_registry):
    """resume() with rejected approval returns feedback as output."""
    class MyState(TestState):
        pass

    class FinalNode(BaseNode[MyState]):
        async def run(self, ctx: GraphRunContext[MyState]) -> End:
            return End("should not reach")

    pending = PendingApproval(
        prompt="Approve?",
        state=MyState(query="test"),
        resume_node=FinalNode(),
    )

    wf = GraphWorkflow(registry=registry, tool_registry=tool_registry)
    result = await wf.resume(pending, ApprovalResult(approved=False, feedback="Needs revision"))

    assert isinstance(result, GraphResult)
    assert "Needs revision" in str(result.output)


@pytest.mark.asyncio
async def test_multi_node_graph(registry, tool_registry):
    """Graph with multiple agent nodes executes in sequence."""
    registry.register(AgentDefinition(name="a", instructions="A.", model="test"))
    registry.register(AgentDefinition(name="b", instructions="B.", model="test"))

    class MyState(TestState):
        pass

    class NodeB(AgentNode[MyState]):
        agent_name: str = "b"
        task: str = "task b"

        async def run(self, ctx: GraphRunContext[MyState]) -> End:
            agent = registry.create("b", tool_registry)
            result = await agent.run("task b", model=make_handler("B result"))
            ctx.state.results.append(result.output)
            return End(" | ".join(ctx.state.results))

    class NodeA(AgentNode[MyState]):
        agent_name: str = "a"
        task: str = "task a"

        async def run(self, ctx: GraphRunContext[MyState]) -> NodeB:
            agent = registry.create("a", tool_registry)
            result = await agent.run("task a", model=make_handler("A result"))
            ctx.state.results.append(result.output)
            return NodeB()

    wf = GraphWorkflow(registry=registry, tool_registry=tool_registry)
    result = await wf.run(NodeA(), MyState(query="test"), model=make_handler())

    assert isinstance(result, GraphResult)
    assert "A result" in result.output
    assert "B result" in result.output


@pytest.mark.asyncio
async def test_workflow_error_on_node_failure(registry, tool_registry):
    """Node failure raises WorkflowError."""
    from easyagents.core.exceptions import WorkflowError

    class MyState(TestState):
        pass

    class FailingNode(BaseNode[MyState]):
        async def run(self, ctx: GraphRunContext[MyState]) -> End:
            raise RuntimeError("Node crashed")

    wf = GraphWorkflow(registry=registry, tool_registry=tool_registry)
    with pytest.raises(WorkflowError):
        await wf.run(FailingNode(), MyState(query="test"))
