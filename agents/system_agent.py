from __future__ import annotations

from agents.base_agent import BaseAgent
from assistant.state import AssistantState
from tools.system_tools import SystemTools

# Agent responsabil pentru informații despre sistemul local.
class SystemAgent(BaseAgent):
    def execute(
        self,
        state: AssistantState,
    ) -> dict[str, str | None]:
        message = state["user_message"].lower()

        try:
            # Verifică dacă utilizatorul cere atât data, cât și ora.
            if any(
                term in message
                for term in (
                    "dată și oră",
                    "data și ora",
                    "data si ora",
                )
            ):
                response = SystemTools.get_datetime()
                
            # Verifică dacă utilizatorul cere doar data.
            elif any(
                term in message
                for term in (
                    "ce dată",
                    "ce data",
                    "data de azi",
                    "ce zi",
                )
            ):
                response = SystemTools.get_date()

            elif any(
                term in message
                for term in (
                    "cât este ora",
                    "cat este ora",
                    "ce oră",
                    "ce ora",
                    "cat este ceasul",
                    "ceas",
                    "ceasul",
                )
            ):
                response = SystemTools.get_time()

            elif any(
                term in message
                for term in (
                    "ram",
                    "memorie ram",
                    "memoria ram",
                    "câtă memorie am",
                    "cata memorie am",
                )
            ):
                response = SystemTools.get_ram()

            elif "procesor" in message or "cpu" in message:
                response = SystemTools.get_cpu()

            elif any(
                term in message
                for term in (
                    "baterie",
                    "battery",
                    "încărcare",
                    "incarcare",
                )
            ):
                response = SystemTools.get_battery()

            else:
                response = (
                    "Pot verifica data, ora, memoria RAM, "
                    "procesorul și bateria."
                )

            return {
                "response": response,
                "error": None,
            }

        except Exception as exc:
            return {
                "response": "",
                "error": (
                    "SystemAgent a întâmpinat o eroare: "
                    f"{exc}"
                ),
            }