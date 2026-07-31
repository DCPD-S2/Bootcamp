from __future__ import annotations

from typing import Literal

from langgraph.graph import END, START, StateGraph

from agents.calculator_agent import CalculatorAgent
from agents.conversation_agent import ConversationAgent
from agents.email_reviewer_agent import EmailReviewerAgent
from agents.email_reviser_agent import EmailReviserAgent
from agents.email_writer_agent import EmailWriterAgent
from agents.search_agent import SearchAgent
from agents.system_agent import SystemAgent
from agents.weather_agent import WeatherAgent
from assistant.router import AssistantRouter
from assistant.state import AgentName, AssistantState
from agents.email_sender_agent import EmailSenderAgent

# Clasa principală care construiește și execută
# fluxul multi-agent al asistentului local.
class LocalAssistantGraph:
    def __init__(
        self,
        model: str = "llama3.1:8b",
    ) -> None:

        # Routerul decide ce ramură trebuie executată.
        self.router = AssistantRouter(model=model)

        # Agenții simpli: fiecare procesează cererea
        # și merge direct la END.
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

        # Agenții care cooperează pe fluxul de email.
        self.email_writer_agent = EmailWriterAgent(
            model=model
        )
        self.email_reviewer_agent = EmailReviewerAgent(
            model=model
        )
        self.email_reviser_agent = EmailReviserAgent(
            model=model
        )
        self.email_sender_agent = EmailSenderAgent()
        # Ultimul email generat este păstrat între cereri.
        self.last_email_subject = ""
        self.last_email_body = ""
        self.last_email_draft = ""
        # Construiește și compilează graful.
        self.graph = self._build_graph()

    def _build_graph(self):
        # Graful folosește AssistantState pentru a transmite
        # datele între toate nodurile.
        builder = StateGraph(AssistantState)

        # Nodul principal de rutare.
        builder.add_node(
            "router",
            self.router.route,
        )

        # Adaugă agenții simpli.
        for agent_name, agent in self.agents.items():
            builder.add_node(
                agent_name,
                agent.execute,
            )

        # Adaugă nodurile cooperative pentru email.
        builder.add_node(
            "email_writer",
            self.email_writer_agent.execute,
        )

        builder.add_node(
            "email_reviewer",
            self.email_reviewer_agent.execute,
        )

        builder.add_node(
            "email_reviser",
            self.email_reviser_agent.execute,
        )

        # Acest nod copiază draftul final în câmpul response.
        builder.add_node(
            "email_finish",
            self._finish_email,
        )
        builder.add_node(
            "email_sender",
            self.email_sender_agent.execute,
        )

        # Graful începe întotdeauna cu routerul.
        builder.add_edge(
            START,
            "router",
        )

        # Routerul decide către ce agent sau flux merge cererea.
        builder.add_conditional_edges(
            "router",
            self._route_after_router,
            {
                "conversation": "conversation",
                "search": "search",
                "weather": "weather",
                "system": "system",
                "calculator": "calculator",

                # Nodurile interne ale fluxului de email.
                "email_writer": "email_writer",
                "email_sender": "email_sender",
            },
        )

        # Agenții simpli merg direct la END.
        for agent_name in self.agents:
            builder.add_edge(
                agent_name,
                END,
            )

        # Fluxul cooperativ pentru email:
        #
        # writer -> reviewer
        builder.add_edge(
            "email_writer",
            "email_reviewer",
        )

        # Reviewerul decide:
        # - email_finish dacă emailul este bun;
        # - email_reviser dacă trebuie corectat.
        builder.add_conditional_edges(
            "email_reviewer",
            self._route_after_email_review,
            {
                "email_finish": "email_finish",
                "email_reviser": "email_reviser",
            },
        )

        # După revizuire, emailul este verificat din nou.
        builder.add_edge(
            "email_reviser",
            "email_reviewer",
        )

        # După pregătirea răspunsului final, graful se termină.
        builder.add_conditional_edges(
            "email_finish",
            self._route_after_email_finish,
            {
                "email_sender": "email_sender",
                "end": END,
            },
        )

        builder.add_edge(
            "email_sender",
            END,
        )

        return builder.compile()

    @staticmethod
    def _route_after_router(
        state: AssistantState,
    ) -> str:
        """
        Selectează nodul care urmează după router.

        Pentru fluxul de email decide dacă trebuie:
        - redactat un email nou;
        - trimis ultimul email deja pregătit.
        """

        selected_agent = state.get(
            "selected_agent",
            "conversation",
        )

        # Ceilalți agenți rămân neschimbați.
        if selected_agent != "email":
            return selected_agent

        message = str(
            state.get("user_message", "")
        ).lower()

        # Formulări care indică redactarea unui email nou.
        compose_terms = (
            "scrie",
            "redactează",
            "redacteaza",
            "formulează",
            "formuleaza",
            "creează",
            "creeaza",
            "un email despre",
            "un mail despre",
            "un e-mail despre",
            "email despre",
            "mail despre",
        )

        # Formulări care indică trimiterea.
        send_terms = (
            "trimite",
            "trimite-l",
            "trimite-o",
            "expediază",
            "expediaza",
            "send",
        )

        # Formulări care indică faptul că utilizatorul
        # se referă la un email redactat anterior.
        previous_email_terms = (
            "emailul anterior",
            "mailul anterior",
            "ultimul email",
            "ultimul mail",
            "emailul pregătit",
            "mailul pregătit",
            "acest email",
            "emailul acesta",
        )

        has_compose_intent = any(
            term in message
            for term in compose_terms
        )

        has_send_intent = any(
            term in message
            for term in send_terms
        )

        refers_to_previous_email = any(
            term in message
            for term in previous_email_terms
        )

        # Dacă utilizatorul spune explicit că vrea
        # emailul anterior, merge direct la sender.
        if has_send_intent and refers_to_previous_email:
            return "email_sender"

        # Dacă cere un email nou, cu sau fără trimitere,
        # trebuie să înceapă cu writerul.
        if has_compose_intent:
            return "email_writer"

        # Dacă spune doar "trimite emailul",
        # folosește ultimul email pregătit.
        if has_send_intent:
            return "email_sender"

        # Implicit, cererile despre email pornesc de la writer.
        return "email_writer"

    @staticmethod
    def _route_after_email_review(
        state: AssistantState,
    ) -> Literal[
        "email_finish",
        "email_reviser",
    ]:
        """
        Decide dacă draftul este gata sau trebuie revizuit.
        """

        # Dacă reviewerul a aprobat emailul,
        # fluxul poate fi finalizat.
        if state.get("email_approved", False):
            return "email_finish"

        # Oprește revizuirile după maximum două încercări,
        # pentru a evita o buclă infinită.
        revision_count = state.get(
            "email_revision_count",
            0,
        )

        if revision_count >= 2:
            return "email_finish"

        return "email_reviser"

    @staticmethod
    def _finish_email(
        state: AssistantState,
    ) -> dict[str, object]:
        """
        Copiază draftul final în câmpul response,
        astfel încât GUI-ul să îl poată afișa.
        """

        email_draft = str(
            state.get("email_draft", "")
        ).strip()

        if not email_draft:
            return {
                "response": "",
                "error": (
                    "Fluxul de email nu a generat "
                    "niciun draft."
                ),
            }

        return {
            "response": email_draft,
            "error": None,
        }

    def invoke(
        self,
        user_message: str,
    ) -> str:
        """
        Execută întregul graf pentru mesajul utilizatorului.
        """

        text = str(user_message).strip()

        if not text:
            raise ValueError(
                "Mesajul utilizatorului este gol."
            )

        # Starea inițială.
        # Câmpurile de email vor fi completate doar dacă
        # routerul selectează ramura email.
        result = self.graph.invoke({
            "user_message": text,
            "selected_agent": "conversation",
            "response": "",
            "error": None,

            "email_draft": self.last_email_draft,
            "email_subject": self.last_email_subject,
            "email_body": self.last_email_body,
            "email_to": "",
            "email_sent": False,
            "email_feedback": "",
            "email_approved": False,
            "email_revision_count": 0,
        })
        self._remember_email(result)
        error = result.get("error")

        if error:
            raise RuntimeError(str(error))

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
        "email",
       
    ]:
        """
        Apelează doar routerul, fără să execute
        agentul sau fluxul selectat.
        """

        result = self.router.route({
            "user_message": user_message,
        })

        return result["selected_agent"]

    def stream(
        self,
        user_message: str,
    ):
        text = str(user_message).strip()

        if not text:
            raise ValueError(
                "Mesajul utilizatorului este gol."
            )

        initial_state = {
            "user_message": text,
            "selected_agent": "conversation",
            "response": "",
            "error": None,
            "email_draft": self.last_email_draft,
            "email_subject": self.last_email_subject,
            "email_body": self.last_email_body,
            "email_to": "",
            "email_sent": False,
            "email_feedback": "",
            "email_approved": False,
            "email_revision_count": 0,
        }

        for event in self.graph.stream(
            initial_state,
            stream_mode="updates",
        ):
            if isinstance(event, dict):
                for update in event.values():
                    if isinstance(update, dict):
                        self._remember_email(update)

            yield event
    
    def _remember_email(
        self,
        state: AssistantState,
    ) -> None:
        """
        Salvează ultimul email generat, astfel încât
        acesta să poată fi trimis într-o cerere ulterioară.
        """

        subject = str(
            state.get("email_subject", "")
        ).strip()

        body = str(
            state.get("email_body", "")
        ).strip()

        draft = str(
            state.get("email_draft", "")
        ).strip()

        if subject:
            self.last_email_subject = subject

        if body:
            self.last_email_body = body

        if draft:
            self.last_email_draft = draft

    @staticmethod
    def _route_after_email_finish(
        state: AssistantState,
    ) -> Literal[
        "email_sender",
        "end",
    ]:
        """
        După redactarea și verificarea emailului,
        decide dacă trebuie doar afișat sau și trimis.
        """

        message = str(
            state.get("user_message", "")
        ).lower()

        send_terms = (
            "trimite",
            "trimite-l",
            "trimite-o",
            "expediază",
            "expediaza",
            "send",
        )

        send_requested = any(
            term in message
            for term in send_terms
        )

        if send_requested:
            return "email_sender"

        return "end"