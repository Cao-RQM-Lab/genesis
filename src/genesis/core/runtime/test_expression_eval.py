from __future__ import annotations

import unittest

from genesis.core.runtime.expression_eval import (
    ExpressionError,
    compileExpression,
    evaluateExpression,
)


class ExpressionEvalTests(unittest.TestCase):
    def test_compile_and_evaluate_with_functions(self) -> None:
        compiled = compileExpression("sqrt(dev1:v) + log10(dev1:i)")
        values = {("dev1", "v"): 9.0, ("dev1", "i"): 100.0}
        actual = evaluateExpression(compiled, values)
        self.assertAlmostEqual(actual, 5.0)

    def test_compile_rejects_unknown_ref_when_restricted(self) -> None:
        with self.assertRaises(ExpressionError):
            compileExpression(
                "dev1:v + dev2:i",
                allowedRefs={("dev1", "v")},
            )

    def test_compile_rejects_unsafe_syntax(self) -> None:
        with self.assertRaises(ExpressionError):
            compileExpression("__import__('os').system('echo nope')")

    def test_missing_dependency_raises(self) -> None:
        compiled = compileExpression("dev1:v + dev1:i")
        with self.assertRaises(ExpressionError):
            evaluateExpression(compiled, {("dev1", "v"): 1.0})

    def test_division_by_zero_raises(self) -> None:
        compiled = compileExpression("dev1:v / dev1:i")
        with self.assertRaises(ExpressionError):
            evaluateExpression(compiled, {("dev1", "v"): 1.0, ("dev1", "i"): 0.0})

    def test_unknown_symbol_rejected(self) -> None:
        with self.assertRaises(ExpressionError):
            compileExpression("time * 2")


if __name__ == "__main__":
    unittest.main()
