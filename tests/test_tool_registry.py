import pytest
from easyagents.core.exceptions import ToolAlreadyRegisteredError, ToolNotFoundError
from easyagents.tools.base import ToolMetadata
from easyagents.tools.registry import ToolRegistry


@pytest.fixture
def registry():
    return ToolRegistry()


def test_register_and_list(registry):
    def my_tool(x: int) -> str:
        return str(x)

    registry.register("my_tool", my_tool)
    tools = registry.list()
    assert len(tools) == 1
    assert tools[0].name == "my_tool"


def test_register_duplicate_raises(registry):
    def tool_a(): pass
    def tool_b(): pass

    registry.register("tool", tool_a)
    with pytest.raises(ToolAlreadyRegisteredError):
        registry.register("tool", tool_b)


def test_resolve_returns_tools(registry):
    def my_tool(x: int) -> str:
        return str(x)

    registry.register("my_tool", my_tool)
    tools = registry.resolve(["my_tool"])
    assert len(tools) == 1


def test_resolve_nonexistent_raises(registry):
    with pytest.raises(ToolNotFoundError):
        registry.resolve(["nonexistent"])


def test_get_returns_metadata(registry):
    def my_tool(x: int) -> str:
        return str(x)

    registry.register("my_tool", my_tool)
    meta = registry.get("my_tool")
    assert isinstance(meta, ToolMetadata)
    assert meta.name == "my_tool"


def test_get_nonexistent_raises(registry):
    with pytest.raises(ToolNotFoundError):
        registry.get("nonexistent")


def test_register_with_custom_description(registry):
    def my_tool(x: int) -> str:
        return str(x)

    registry.register("my_tool", my_tool, description="Custom desc")
    meta = registry.get("my_tool")
    assert meta.description == "Custom desc"
