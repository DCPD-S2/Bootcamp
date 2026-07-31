from __future__ import annotations
import ast 
import math
import operator
import re
from typing import Callable


class CalculatorTools:
    # Dicționar care asociază operatorii AST binari
    # cu funcțiile Python care efectuează calculul.
    _binary_operators: dict[
        type[ast.operator],
        Callable[[float, float], float],
    ] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }

    _unary_operators: dict[
        type[ast.unaryop],
        Callable[[float], float],
    ] = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }

    _functions: dict[str, Callable[..., float]] = {
        "sqrt": math.sqrt,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "log": math.log,
        "log10": math.log10,
        "abs": abs,
        "round": round,
    }

    _constants = {
        "pi": math.pi,
        "e": math.e,
    }

    @classmethod
    def calculate(cls, expression: str) -> float:
        expression = cls.normalize_expression(expression)
        if not expression:
            raise ValueError("Expresia matematică este goală.")
        
        # Transformă expresia într-un arbore AST.
        tree = ast.parse(expression, mode="eval")
        result = cls._evaluate_node(tree.body)

        if not math.isfinite(float(result)):
            raise ValueError("Rezultatul nu este un număr finit.")

        return float(result)

    @classmethod
    def normalize_expression(cls, text: str) -> str:
        value = text.lower().strip()
        # Înlocuiește expresii cu operatori matematici.
        replacements = {
            "calculează": "",
            "calculeaza": "",
            "cât este": "",
            "cat este": "",
            "înmulțit cu": "*",
            "inmultit cu": "*",
            "ori": "*",
            "împărțit la": "/",
            "impartit la": "/",
            "plus": "+",
            "minus": "-",
            "^": "**",
            "radical din": "sqrt",
        }

        for source, destination in replacements.items():
            value = value.replace(source, destination)

        value = value.replace(",", ".")

        # Transformă „sqrt 25” în „sqrt(25)”.
        value = re.sub(
            r"\bsqrt\s+(-?\d+(?:\.\d+)?)",
            r"sqrt(\1)",
            value,
        )

        return value.strip(" ?=")

    @classmethod
    def _evaluate_node(cls, node: ast.AST) -> float:
        if isinstance(node, ast.Constant):
            if not isinstance(node.value, (int, float)):
                raise ValueError("Valoare neacceptată.")
            return float(node.value)

        if isinstance(node, ast.BinOp):
            operation = cls._binary_operators.get(
                type(node.op)
            )
            if operation is None:
                raise ValueError("Operator neacceptat.")

            left = cls._evaluate_node(node.left)
            right = cls._evaluate_node(node.right)

            if isinstance(node.op, ast.Pow) and abs(right) > 100:
                raise ValueError("Exponentul este prea mare.")

            return float(operation(left, right))

        if isinstance(node, ast.UnaryOp):
            operation = cls._unary_operators.get(
                type(node.op)
            )
            if operation is None:
                raise ValueError("Operator unar neacceptat.")

            return float(
                operation(cls._evaluate_node(node.operand))
            )

        if isinstance(node, ast.Name):
            if node.id not in cls._constants:
                raise ValueError(
                    f"Constanta «{node.id}» nu este acceptată."
                )
            return float(cls._constants[node.id])

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("Funcție neacceptată.")

            function = cls._functions.get(node.func.id)
            if function is None:
                raise ValueError(
                    f"Funcția «{node.func.id}» nu este acceptată."
                )

            arguments = [
                cls._evaluate_node(argument)
                for argument in node.args
            ]

            return float(function(*arguments))

        raise ValueError(
            "Expresia conține elemente neacceptate."
        )