from __future__ import annotations
from langchain_ollama import ChatOllama

from agents.base_agent import BaseAgent
from assistant.state import AssistantState

# Agent responsabil pentru conversațiile generale.
class ConversationAgent(BaseAgent):
    def __init__(
        self,
        model: str = "llama3.1:8b",
    ) -> None:
        self.llm = ChatOllama( # Inițializează modelul LLM care va genera răspunsurile.
            model=model,
            temperature=0.4, # oferă răspunsuri naturale,
        )

    def execute(
        self,
        state: AssistantState,
    ) -> dict[str, str | None]:
        try:
            result = self.llm.invoke([
                (
                    "system",
                    """
                    Ești un asistent AI local util și prietenos.

                    Răspunde în limba utilizatorului.
                    Explică natural și clar.
                    Nu pretinde că ai căutat pe internet.
                    Nu inventa informații recente.
                    Pentru întrebări generale, oferă răspunsuri concise,
                    dar suficient de explicate.
                    """.strip(),
                ),
                (
                    "human",
                    state["user_message"],   # Mesajul utilizatorului extras din AssistantState.
                ),
            ])
            # Actualizează AssistantState cu răspunsul generat.
            return {
                "response": str(result.content).strip(),
                "error": None,
            }

        except Exception as exc:
            return {
                "response": "",
                "error": (
                    "ConversationAgent nu a putut genera "
                    f"răspunsul: {exc}"
                ),
            }