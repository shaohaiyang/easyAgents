from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolMetadata:
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
