import pytest
from dataclasses import dataclass
from pydantic import BaseModel
from pydantic_ai import ModelResponse, TextPart, RunUsage
from pydantic_ai.models.function import FunctionModel, AgentInfo
from pydantic_graph import BaseNode, GraphRunContext, End

from easyagents import (
    AgentDefinition, AgentRegistry, ToolRegistry,
    GraphWorkflow, GraphResult, PendingApproval, ApprovalResult,
    DynamicOrchestrator,
)


class WorkflowState(BaseModel):
    query: str = ""
    results: list[str] = []
    usage: RunUsage = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.usage is None:
            self.usage = RunUsage()


def make_handler(output: str = "OK"):
    def handler(messages, info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(content=output)])
    return FunctionModel(handler)


@pytest.mark.asyncio
async def test_graph_workflow_with_approval_end_to_end():
    """Full flow: agent node -> approval -> resume -> final node."""
    tools = ToolRegistry()
    agents = AgentRegistry()
    agents.register(AgentDefinition(name="worker", instructions="Work.", model="test"))

    class State(WorkflowState):
        pass

    class FinalNode(BaseNode[State]):
        async def run(self, ctx: GraphRunContext[State]) -> End:
            return End("completed successfully")

    class WorkNode(BaseNode[State]):
        async def run(self, ctx: GraphRunContext[State]) -> "ApprovalNode[State]":
            agent = agents.create("worker", tools)
            result = await agent.run("do work", model=make_handler("Work done"))
            ctx.state.results.append(result.output)
            return ApprovalNode(prompt="Approve work?", next_node=FinalNode())

    @dataclass
    class ApprovalNode(BaseNode[State]):
        prompt: str
        next_node: BaseNode[State]

        async def run(self, ctx: GraphRunContext[State]) -> End:
            return End(PendingApproval(
                prompt=self.prompt,
                state=ctx.state,
                resume_node=self.next_node,
            ))

    wf = GraphWorkflow(registry=agents, tool_registry=tools)

    # Run -> pauses at approval
    result = await wf.run(WorkNode(), State(query="test"), model=make_handler("Work done"))
    assert isinstance(result, PendingApproval)
    assert "Work done" in result.state.results

    # Resume after approval
    final = await wf.resume(result, ApprovalResult(approved=True), model=make_handler())
    assert isinstance(final, GraphResult)
    assert final.output == "completed successfully"


@pytest.mark.asyncio
async def test_dynamic_orchestrator_end_to_end():
    """Full flow: decompose -> parallel execution."""
    import json

    tools = ToolRegistry()
    agents = AgentRegistry()
    agents.register(AgentDefinition(name="researcher", instructions="Research.", model="test", description="调研"))
    agents.register(AgentDefinition(name="writer", instructions="Write.", model="test", description="写作"))

    subtasks_json = json.dumps([
        {"agent": "researcher", "task": "Find data", "rationale": "Need data"},
        {"agent": "writer", "task": "Write it up", "rationale": "Need report"},
    ])

    def handler(messages, info: AgentInfo) -> ModelResponse:
        content = ""
        for part in messages[-1].parts:
            content += str(getattr(part, "content", ""))
        if "decomposer" in content.lower() or "Break" in content:
            return ModelResponse(parts=[TextPart(content=subtasks_json)])
        return ModelResponse(parts=[TextPart(content="Subtask done")])

    dyn = DynamicOrchestrator(
        agents=["researcher", "writer"],
        registry=agents,
        tool_registry=tools,
        model="test",
    )

    result = await dyn.run("调研并写报告", model=FunctionModel(handler))

    assert len(result.subtask_results) == 2


@pytest.mark.asyncio
async def test_checkpoint_with_graph_workflow():
    """CheckpointManager saves state during graph execution."""
    from easyagents import CheckpointManager

    tools = ToolRegistry()
    agents = AgentRegistry()
    agents.register(AgentDefinition(name="worker", instructions="Work.", model="test"))

    mgr = CheckpointManager()

    class State(WorkflowState):
        pass

    class SimpleNode(BaseNode[State]):
        async def run(self, ctx: GraphRunContext[State]) -> End:
            agent = agents.create("worker", tools)
            result = await agent.run("work", model=make_handler("Done"))
            ctx.state.results.append(result.output)
            await mgr.save("wf-1", "SimpleNode", ctx.state)
            return End("finished")

    wf = GraphWorkflow(registry=agents, tool_registry=tools, checkpoint_manager=mgr)
    result = await wf.run(SimpleNode(), State(query="test"), model=make_handler("Done"))

    assert result.output == "finished"
    checkpoints = await mgr.list_checkpoints("wf-1")
    assert len(checkpoints) == 1
    cp = await mgr.load(checkpoints[0])
    assert "Done" in str(cp.state)
