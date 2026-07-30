from typing import Optional


def configure(
    logfire_token: Optional[str] = None,
    service_name: str = "easyagents",
) -> None:
    """Configure Logfire observability for EasyAgents.

    Sets up Logfire and instruments Pydantic AI for automatic tracing
    of agent runs, tool calls, and delegation.

    Args:
        logfire_token: Logfire cloud token. If None, logs to stderr (development mode).
        service_name: Service name for identifying traces.
    """
    import logfire
    from logfire.exceptions import LogfireConfigError

    try:
        logfire.configure(
            token=logfire_token,
            service_name=service_name,
        )
        logfire.instrument_pydantic_ai()
    except LogfireConfigError:
        pass  # Gracefully degrade if Logfire is not configured
