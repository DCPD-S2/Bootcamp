from __future__ import annotations

from typing import Literal

from langgraph.graph import END, START, StateGraph

from agents.calculator_agent import CalculatorAgent
from agents.conversation_agent import ConversationAgent
from agents.search_agent import SearchAgent
from agents.system_agent import SystemAgent
from agents.weather_agent import WeatherAgent
from assistant.router import AssistantRouter
from assistant.state import AgentName, AssistantState


# Clasa principală care construiește și execută fluxul multi-agent al asistentului local.
class LocalAssistantGraph:
    def __init__(
        self,
        model: str = "llama3.1:8b",
    ) -> None:

        # Inițializează routerul care decide ce agent trebuie să proceseze cererea.
        self.router = AssistantRouter(model=model)
        # Creează toate instanțele agenților disponibili.
        self.agents = {
            "conversation": ConversationAgent(model=model),
            "search": SearchAgent(
                model=model,
                maximum_results=5,
            ),
            "weather": WeatherAgent(model=model),
            "system": SystemAgent(),
            "calculator": CalculatorAgent(model=model),
        }
        # Construiește și compilează graful LangGraph.
        self.graph = self._build_graph()

    def _build_graph(self):
        # Creează un graf nou care folosește AssistantState pentru starea transmisă între noduri.
        builder = StateGraph(AssistantState)

        # Adaugă routerul ca nod în graf.
        builder.add_node(
            "router",
            self.router.route,
        )

        # Adaugă fiecare agent ca nod separat.
        for agent_name, agent in self.agents.items():
            builder.add_node(
                agent_name,
                agent.execute,
            )

        # Definește punctul de intrare în graf:
        builder.add_edge(START, "router")

        builder.add_conditional_edges(
            "router",
            self._route_after_router,
            {
                "conversation": "conversation",
                "search": "search",
                "weather": "weather",
                "system": "system",
                "calculator": "calculator",
            },
        )
        # După ce un agent termină execuția, fluxul ajunge direct la END.
        for agent_name in self.agents:
            builder.add_edge(agent_name, END)

        return builder.compile()

    @staticmethod
    # Citește agentul ales de router.
    def _route_after_router(
        state: AssistantState,
    ) -> AgentName:
        return state.get(
            "selected_agent",
            "conversation",
        )

    # Execută întregul graf.
    def invoke(self, user_message: str) -> str:
        text = str(user_message).strip()

        if not text:
            raise ValueError(
                "Mesajul utilizatorului este gol."
            )
        # Starea initială
        result = self.graph.invoke({
            "user_message": text,
            "selected_agent": "conversation",
            "response": "",
            "error": None,
        })

        error = result.get("error")
        if error:
            raise RuntimeError(error)
         
        # Extrage răspunsul final din starea grafului.
        response = str(
            result.get("response", "")
        ).strip()

        if not response:
            raise RuntimeError(
                "Agentul nu a returnat niciun răspuns."
            )

        return response

    def inspect_route(
        self,
        user_message: str,
    ) -> Literal[
        "conversation",
        "search",
        "weather",
        "system",
        "calculator",
    ]:
        # Apelează doar routerul, fără să execute
        # agentul selectat și fără să ruleze întregul graf.
        result = self.router.route({
            "user_message": user_message,
        })

        return result["selected_agent"]