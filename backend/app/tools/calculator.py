import ast
import operator
from typing import Any

from app.tools.base import BaseTool, ToolDefinition

_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_ALLOWED_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
_MAX_EXPONENT = 1000  # guards against a**b blowing up into an astronomically large int


def _evaluate(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _evaluate(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise ValueError(f"Unsupported constant: {node.value!r}")
    if isinstance(node, ast.BinOp):
        op = _ALLOWED_BINOPS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        left, right = _evaluate(node.left), _evaluate(node.right)
        if type(node.op) is ast.Pow and abs(right) > _MAX_EXPONENT:
            raise ValueError("Exponent too large")
        return op(left, right)
    if isinstance(node, ast.UnaryOp):
        op = _ALLOWED_UNARYOPS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return op(_evaluate(node.operand))
    raise ValueError(f"Unsupported expression: {type(node).__name__}")


def evaluate_expression(expression: str) -> float:
    """Safely evaluates a numeric arithmetic expression - deliberately not `eval()`: the AST is
    walked and only literal numbers, +-*/%**, unary +/-, and parentheses are permitted, so
    attribute/name/call nodes (the building blocks of an arbitrary-code-execution payload like
    `__import__('os').system(...)`) are rejected before they can run."""
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"Invalid expression: {exc}") from exc
    try:
        return _evaluate(tree)
    except ZeroDivisionError as exc:
        raise ValueError("Division by zero") from exc


class CalculatorTool(BaseTool):
    definition = ToolDefinition(
        name="calculator",
        description="Evaluates a numeric arithmetic expression (+, -, *, /, %, **, parentheses).",
        input_schema={
            "type": "object",
            "properties": {"expression": {"type": "string", "description": "e.g. '(2 + 3) * 4'"}},
            "required": ["expression"],
        },
        permission_level="public",
        timeout_seconds=5.0,
    )

    async def run(self, **kwargs: Any) -> float:
        expression = kwargs.get("expression")
        if not isinstance(expression, str) or not expression.strip():
            raise ValueError("'expression' must be a non-empty string")
        return evaluate_expression(expression)
