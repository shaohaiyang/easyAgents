"""Demo: show how EasyAgents multi-agent delegation works."""
from pydantic import BaseModel
from pydantic_ai.models.test import TestModel

from easyagents import (
    AgentDefinition,
    AgentRegistry,
    SessionManager,
    ToolRegistry,
    configure,
)


class ResearchFindings(BaseModel):
    products: list[str]
    summary: str


def main():
    configure(service_name="easyagents-demo")

    tools = ToolRegistry()
    tools.register("web_search", lambda q: [
        {"title": "AirPods Pro 2", "url": "https://apple.com", "snippet": "Apple's flagship TWS earbuds"}
    ])

    agents = AgentRegistry()
    agents.register(AgentDefinition(
        name="researcher",
        instructions="Research products using web_search.",
        model="test",
        tools=["web_search"],
        output_type=ResearchFindings,
    ))
    agents.register(AgentDefinition(
        name="orchestrator",
        instructions="Use delegate_researcher to research, then summarize.",
        model="test",
        subagents=["researcher"],
    ))

    session_mgr = SessionManager()
    session = session_mgr.create()
    print(f"Session ID: {session.conversation_id}")

    agent = agents.create("orchestrator", tools)

    result = agent.run_sync(
        "调研最近爆火的蓝牙耳机",
        model=TestModel(custom_output_text=str(ResearchFindings(
            products=["AirPods Pro 2", "Sony WF-1000XM5"],
            summary="Two top competitors.",
        ))),
    )

    session_mgr.save_messages(session.conversation_id, result.all_messages())

    print(f"Output: {result.output}")
    print(f"Messages: {len(session.messages)}")
    print(f"Usage: {result.usage}")
    print("Done!")


if __name__ == "__main__":
    main()
