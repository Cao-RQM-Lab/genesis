from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass


class ExpressionError(ValueError):
    pass


_VAR_REF_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])([A-Za-z0-9_.-]+):([A-Za-z0-9_.-]+)(?![A-Za-z0-9_])"
)

_ALLOWED_FUNCS: dict[str, object] = {
    "abs": abs,
    "min": min,
    "max": max,
    "sqrt": math.sqrt,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
}

_ALLOWED_CONSTS: dict[str, float] = {
    "pi": math.pi,
    "e": math.e,
}

_ALLOWED_BINOPS = (
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
)
_ALLOWED_UNARYOPS = (ast.UAdd, ast.USub)


@dataclass(frozen=True, slots=True)
class CompiledExpression:
    rawExpr: str
    normalizedExpr: str
    code: object
    tokenByRef: dict[tuple[str, str], str]
    refByToken: dict[str, tuple[str, str]]

    @property
    def dependencies(self) -> set[tuple[str, str]]:
        return set(self.tokenByRef.keys())


def refToToken(instrumentId: str, key: str) -> str:
    inst = re.sub(r"[^A-Za-z0-9_]", "_", instrumentId)
    sig = re.sub(r"[^A-Za-z0-9_]", "_", key)
    return f"v_{inst}__{sig}"


def tokenToRefString(instrumentId: str, key: str) -> str:
    return f"{instrumentId}:{key}"


def compileExpression(
    expr: str,
    *,
    allowedRefs: set[tuple[str, str]] | None = None,
) -> CompiledExpression:
    rawExpr = str(expr).strip()
    if not rawExpr:
        raise ExpressionError("Expression is empty.")

    tokenByRef: dict[tuple[str, str], str] = {}
    refByToken: dict[str, tuple[str, str]] = {}

    def _replace(match: re.Match[str]) -> str:
        ref = (match.group(1), match.group(2))
        if allowedRefs is not None and ref not in allowedRefs:
            raise ExpressionError(f"Unknown variable reference: {ref[0]}:{ref[1]}")
        token = tokenByRef.get(ref)
        if token is None:
            token = refToToken(ref[0], ref[1])
            tokenByRef[ref] = token
            refByToken[token] = ref
        return token

    try:
        normalized = _VAR_REF_PATTERN.sub(_replace, rawExpr)
    except ExpressionError:
        raise

    try:
        parsed = ast.parse(normalized, mode="eval")
    except SyntaxError as exc:
        raise ExpressionError(f"Invalid expression syntax: {exc.msg}") from exc

    _validateAst(parsed, allowedTokens=set(refByToken.keys()))

    code = compile(parsed, "<plot-expression>", "eval")
    return CompiledExpression(
        rawExpr=rawExpr,
        normalizedExpr=normalized,
        code=code,
        tokenByRef=tokenByRef,
        refByToken=refByToken,
    )


def evaluateExpression(
    compiled: CompiledExpression,
    latestValues: dict[tuple[str, str], float],
) -> float:
    env: dict[str, object] = dict(_ALLOWED_FUNCS)
    env.update(_ALLOWED_CONSTS)

    for ref, token in compiled.tokenByRef.items():
        if ref not in latestValues:
            raise ExpressionError(f"Missing value for {ref[0]}:{ref[1]}")
        env[token] = float(latestValues[ref])

    try:
        value = eval(compiled.code, {"__builtins__": {}}, env)
    except ZeroDivisionError as exc:
        raise ExpressionError("Division by zero in expression.") from exc
    except Exception as exc:
        raise ExpressionError(f"Expression evaluation failed: {exc}") from exc

    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ExpressionError(
            "Expression did not evaluate to a numeric value."
        ) from exc


def _validateAst(node: ast.AST, *, allowedTokens: set[str]) -> None:
    if isinstance(node, ast.Expression):
        _validateAst(node.body, allowedTokens=allowedTokens)
        return

    if isinstance(node, ast.BinOp):
        if not isinstance(node.op, _ALLOWED_BINOPS):
            raise ExpressionError("Operator is not allowed.")
        _validateAst(node.left, allowedTokens=allowedTokens)
        _validateAst(node.right, allowedTokens=allowedTokens)
        return

    if isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, _ALLOWED_UNARYOPS):
            raise ExpressionError("Unary operator is not allowed.")
        _validateAst(node.operand, allowedTokens=allowedTokens)
        return

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ExpressionError("Only direct function calls are allowed.")
        if node.func.id not in _ALLOWED_FUNCS:
            raise ExpressionError(f"Function '{node.func.id}' is not allowed.")
        if node.keywords:
            raise ExpressionError("Keyword arguments are not supported.")
        for arg in node.args:
            _validateAst(arg, allowedTokens=allowedTokens)
        return

    if isinstance(node, ast.Name):
        if node.id in _ALLOWED_CONSTS:
            return
        if node.id not in allowedTokens:
            raise ExpressionError(f"Unknown symbol '{node.id}'.")
        return

    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return
        raise ExpressionError("Only numeric literals are allowed.")

    raise ExpressionError("Expression contains unsupported syntax.")
