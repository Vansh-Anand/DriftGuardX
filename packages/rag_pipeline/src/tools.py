from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class BaseTool(ABC):
    name: str
    description: str
    schema: type[BaseModel]
    safe_for_replay: bool = True

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Any:
        pass


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "schema": tool.schema.model_json_schema(),
                "safe_for_replay": tool.safe_for_replay,
            }
            for tool in self._tools.values()
        ]


# Example Tool
class CalculateSchema(BaseModel):
    expression: str


class CalculateTool(BaseTool):
    name = "calculate"
    description = "Evaluates a mathematical expression safely."
    schema = CalculateSchema
    safe_for_replay = True

    async def execute(self, expression: str, **kwargs: Any) -> Any:
        try:
            # For demo purposes. In real life, use a safe eval.
            allowed_names = {"__builtins__": None}
            result = eval(expression, allowed_names, {})
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}


registry = ToolRegistry()
registry.register(CalculateTool())
