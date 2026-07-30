import pytest
from easyagents.observability.tracing import configure


def test_configure_runs_without_error():
    configure(service_name="test-easyagents")


def test_configure_is_idempotent():
    configure(service_name="test-easyagents")
    configure(service_name="test-easyagents")
