from __future__ import annotations
from langchain_ollama import ChatOllama

from agents.base_agent import BaseAgent
from assistant.state import AssistantState
from tools.search_tools import SearchTools

# Agent responsabil pentru căutarea informațiilor pe internet.
class SearchAgent(BaseAgent):
    def __init__(
        self,
        model: str = "llama3.1:8b",
        maximum_results: int = 5,
    ) -> None:
        # Numărul maxim de rezultate care vor fi analizate.
        self.maximum_results = maximum_results

        self.llm = ChatOllama(
            model=model,
            temperature=0.2,
        )

    def execute(
        self,
        state: AssistantState,
    ) -> dict[str, str | None]:
        query = state["user_message"]

        try:
            # Efectuează căutarea pe internet.
            results = SearchTools.search(
                query,
                maximum_results=self.maximum_results,
            )

            # Dacă nu există rezultate, întoarce un mesaj corespunzător.
            if not results:
                return {
                    "response": (
                        "Nu am găsit rezultate relevante."
                    ),
                    "error": None,
                }
        
            context = SearchTools.build_context(results)
            # Utilizează SearchTools pentru a obține rezultatele, iar apoi LLM-ul generează un răspuns bazat exclusiv pe acestea.
            answer = self.llm.invoke([
                (
                    "system",
                    """
                    Ești SearchAgent.

                    Răspunde folosind numai informațiile din rezultatele
                    căutării furnizate.

                    Reguli:
                    - nu inventa informații;
                    - nu afișa linkurile în răspuns;
                    - combină informațiile fără repetiții;
                    - răspunde în limba utilizatorului;
                    - menționează când rezultatele sunt neclare
                    sau insuficiente;
                    - oferă un răspuns natural și concis.
                    """.strip(),
                ),
                (
                    "human",
                    f"""
                    Întrebarea utilizatorului:
                    {query}

                    Rezultatele căutării:
                    {context}
                    """.strip(),
                ),
            ])

            return {
                "response": str(answer.content).strip(),
                "error": None,
            }

        except Exception as exc:
            return {
                "response": "",
                "error": (
                    "SearchAgent nu a putut finaliza "
                    f"căutarea: {exc}"
                ),
            }