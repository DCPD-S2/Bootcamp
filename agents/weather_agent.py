from __future__ import annotations

from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field
from typing import Literal
from agents.base_agent import BaseAgent
from assistant.state import AssistantState
from tools.weather_tools import WeatherTools

# Structura răspunsului returnat de LLM.
class WeatherRequest(BaseModel):
    city: str | None = Field(
        default=None,
        description="Orașul solicitat de utilizator.",
    )
    request_type: Literal["weather", "forecast"] = Field(
        description=(
            "weather pentru vremea actuală sau "
            "forecast pentru o zi viitoare."
        )
    )
    days_ahead: int = Field(
        default=0,
        ge=0,
        description=(
            "Numărul de zile față de astăzi. "
            "Astăzi=0, mâine=1, poimâine=2, "
            "peste 5 zile=5."
        ),
    )

class WeatherAgent(BaseAgent):
    def __init__(
        self,
        model: str = "llama3.1:8b",
    ) -> None:
        llm = ChatOllama(
            model=model,
            temperature=0,
        )

        self.parser = llm.with_structured_output(
            WeatherRequest
        )

    def execute(
        self,
        state: AssistantState,
    ) -> dict[str, str | None]:
        try:
            # LLM-ul analizează întrebarea și extrage: orașul, tipul cererii (weather / forecast).
            request = self.parser.invoke([
                (
                    "system",
                    """
                    Extrage orașul, tipul cererii și numărul de zile față de data curentă.

                    Reguli pentru request_type:
                    - weather pentru vremea actuală;
                    - forecast pentru orice zi viitoare.

                    Reguli pentru days_ahead:
                    - astăzi sau acum -> 0;
                    - mâine -> 1;
                    - poimâine -> 2;
                    - peste N zile -> N.

                    Copiază exact numele orașului menționat
                    de utilizator.

                    Exemple:

                    „Cum este vremea acum în București?”
                    city = "București"
                    request_type = "weather"
                    days_ahead = 0

                    „Cum este vremea mâine în Brașov?”
                    city = "Brașov"
                    request_type = "forecast"
                    days_ahead = 1

                    „Cum va fi vremea poimâine în Cluj?”
                    city = "Cluj"
                    request_type = "forecast"
                    days_ahead = 2

                    „Cum va fi vremea peste 5 zile în Iași?”
                    city = "Iași"
                    request_type = "forecast"
                    days_ahead = 5
                    """.strip(),
                ),
                (
                    "human",
                    state["user_message"],
                ),
            ])
            
            if request is None:
                raise ValueError(
                    "Nu am putut interpreta cererea meteo."
                )

            if request.city is None or not request.city.strip():
                raise ValueError(
                    "Nu ai specificat orașul."
                )

            if request.request_type == "forecast":
                response = WeatherTools.get_forecast(
                    request.city,
                    days_ahead=request.days_ahead,
                )
            else:
                response = WeatherTools.get_weather(
                    request.city
                )
            

            return {
                "response": response,
                "error": None,
            }

        except Exception as exc:
            return {
                "response": "",
                "error": (
                    "WeatherAgent nu a putut obține vremea: "
                    f"{exc}"
                ),
            }