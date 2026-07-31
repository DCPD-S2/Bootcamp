from __future__ import annotations
from typing import Literal
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field

from assistant.state import AgentName, AssistantState


# Routerul trebuie să aleagă exact un agent care va procesa cererea.
class RoutingDecision(BaseModel):
    agent: Literal[
        "conversation",
        "search",
        "weather",
        "system",
        "calculator",
        "email",
    ] = Field(
        description="Agentul care trebuie să proceseze cererea."
    )


class AssistantRouter:
    def __init__(
        self,
        model: str = "llama3.1:8b",
    ) -> None:
     # Inițializează modelul LLM utilizat pentru clasificarea cererilor utilizatorului.
        llm = ChatOllama(
            model=model,
            temperature=0,
        )

     # Configurează modelul astfel încât răspunsul să respecte structura RoutingDecision.
        self._structured_llm = llm.with_structured_output(RoutingDecision)


    # Primește mesajul utilizatorului și stabilește ce agent trebuie să proceseze cererea.
    def route(self, state: AssistantState) -> dict[str, AgentName]:
        user_message = state["user_message"] # Extrage mesajul introdus de utilizator din starea aplicației.
        prompt = [
            (
                "system",
                """
                Ești routerul unui asistent AI local.

                Alege exact un agent:

                - conversation:
                conversație generală, explicații, definiții, redactare,
                brainstorming și întrebări care nu necesită informații actuale.

                - search:
                informații de pe internet, știri, informații recente,
                verificarea unor informații sau cereri care conțin
                expresii precum «caută», «ultimele informații» sau «știri».

                - weather:
                vreme actuală, temperatură, precipitații și prognoză.

                - system:
                oră, dată, ziua curentă și informații despre calculator.

                - calculator:
                calcule matematice, procente, expresii și conversii numerice.

                - email:
                toate operațiile referitoare la email:
                redactarea, corectarea, formularea sau trimiterea
                unui email deja pregătit.                

                Returnează numai structura cerută.
                """.strip(),
            ),
            ("human", user_message),
        ]

        try:
            decision = self._structured_llm.invoke(prompt) # Trimite promptul către LLM.

            if decision is None:
                return {"selected_agent": "conversation"}

            return {"selected_agent": decision.agent}

        except Exception:
            # Nu blocăm aplicația dacă modelul nu produce structured output valid.
            return {
                "selected_agent": self._fallback_route(
                    user_message
                )
            }

    @staticmethod
    def _fallback_route(message: str) -> AgentName:
        normalized = message.lower()

        weather_terms = {
            "vreme",
            "temperatura",
            "temperatură",
            "prognoza",
            "prognoză",
            "plouă",
            "ninsoare",
        }

        system_terms = {
            "ora",
            "oră",
            "data",
            "ce zi",
            "procesor",
            "memorie ram",
            "baterie",
        }

        search_terms = {
            "caută",
            "cauta",
            "știri",
            "stiri",
            "ultimele",
            "recent",
            "internet",
            "online",
        }

        calculator_terms = {
            "calculează",
            "calculeaza",
            "radical",
            "procent",
            "înmulțit",
            "inmultit",
            "împărțit",
            "impartit",
        }


        email_terms = {
            "email",
            "e-mail",
            "mail",
            "redactează",
            "redacteaza",
            "scrie un mesaj",
            "scrie un email",
            "redactează un email",
            "redacteaza un email",
            "formulează un email",
            "formuleaza un email",
            "scrie un mesaj",
            "trimite",
            "expediază",
            "expediaza",
        }

        if any(
            term in normalized
            for term in weather_terms
        ):
            return "weather"

        if any(
            term in normalized
            for term in system_terms
        ):
            return "system"

        if any(
            term in normalized
            for term in search_terms
        ):
            return "search"

        if any(
            term in normalized
            for term in calculator_terms
        ):
            return "calculator"

        if any(
            term in normalized
            for term in email_terms
        ):
            return "email"

        return "conversation"