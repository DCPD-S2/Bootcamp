from __future__ import annotations
from langchain_ollama import ChatOllama
#ChatOllama este clasa LangChain care permite comunicarea cu un model care rulează local prin Ollama.
from pydantic import BaseModel, Field

from agents.base_agent import BaseAgent
from assistant.state import AssistantState
from tools.calculator_tools import CalculatorTools

# Structura rezultatului pe care LLM-ul trebuie să îl genereze.
# Modelul extrage din limbaj natural doar expresia matematică.
class CalculationRequest(BaseModel):
    expression: str = Field(
        description=(
            "Expresia matematică Python, fără explicații. "
            "Exemplu: sqrt(625), 45 * 73 sau 15 / 100 * 240."
        )
    )

# Agent specializat în interpretarea și executarea cererilor de calcul matematic.
class CalculatorAgent(BaseAgent):
    def __init__(
        self,
        model: str = "llama3.1:8b",
    ) -> None:
        llm = ChatOllama(
            model=model,
            temperature=0,
        )

        self.parser = llm.with_structured_output(
            CalculationRequest
        )

    def execute(
        self,
        state: AssistantState,
    ) -> dict[str, str | None]:
        user_message = state["user_message"]

        try:
            parsed = self.parser.invoke([  # Trimite instrucțiunile și întrebarea către model.
                (
                    "system",
                    """
                    Extrage expresia matematică din cererea utilizatorului.

                    Folosește:
                    + - * / // % **
                    sqrt, sin, cos, tan, log, log10, abs, round, pi, e.

                    Nu calcula rezultatul.
                    Nu adăuga explicații.
                    """.strip(),
                ),
                ("human", user_message),
            ])

            if parsed is None:
                expression = user_message
            else:
                expression = parsed.expression

            result = CalculatorTools.calculate(expression)

            if result.is_integer():
                formatted = str(int(result))
            else:
                formatted = f"{result:.10g}"

            return {
                "response": (
                    f"Rezultatul este {formatted}."
                ),
                "error": None,
            }

        except Exception as exc:
            return {
                "response": "",
                "error": (
                    "Nu am putut calcula expresia: "
                    f"{exc}"
                ),
            }