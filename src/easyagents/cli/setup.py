from easyagents import AgentRegistry, ToolRegistry, web_search, http_request, write_file


def create_registry():
    """Create and configure registries with built-in tools."""
    tools = ToolRegistry()
    tools.register("web_search", web_search)
    tools.register("http_request", http_request)
    tools.register("write_file", write_file)
    agents = AgentRegistry()
    return agents, tools
