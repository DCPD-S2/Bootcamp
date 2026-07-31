from __future__ import annotations

from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field

from agents.base_agent import BaseAgent
from assistant.state import AssistantState


class GeneratedEmail(BaseModel):
    subject: str = Field(
        description="Subiectul emailului, fără prefixul «Subiect:»."
    )

    body: str = Field(
        description=(
            "Corpul complet al emailului, cu formulă de adresare "
            "și încheiere, dar fără subiect."
        )
    )


class EmailWriterAgent(BaseAgent):
    def __init__(
        self,
        model: str = "llama3.1:8b",
    ) -> None:
        llm = ChatOllama(
            model=model,
            temperature=0.3,
        )

        # LLM-ul trebuie să returneze un obiect GeneratedEmail.
        self.writer = llm.with_structured_output(
            GeneratedEmail
        )

    def execute(
        self,
        state: AssistantState,
    ) -> dict[str, object]:
        try:
            email = self.writer.invoke([
                (
                    "system",
                    """
                    Redactează un email pe baza cererii utilizatorului.

                    Returnează separat:
                    - subject: subiectul emailului;
                    - body: corpul emailului.

                    Reguli:
                    - respectă tonul solicitat;
                    - răspunde în limba utilizatorului;
                    - nu inventa informații;
                    - nu inventa semnătura utilizatorului;
                    - nu include prefixul „Subiect:” în câmpul subject;
                    - nu include subiectul în câmpul body;
                    - corpul trebuie să conțină formulă de adresare,
                      conținut și încheiere;
                    - nu adăuga explicații în afara emailului.
                    """.strip(),
                ),
                (
                    "human",
                    state["user_message"],
                ),
            ])

            if email is None:
                raise ValueError(
                    "Modelul nu a generat emailul."
                )

            subject = email.subject.strip()
            body = email.body.strip()

            if not subject:
                raise ValueError(
                    "Emailul generat nu are subiect."
                )

            if not body:
                raise ValueError(
                    "Emailul generat nu are conținut."
                )

            # email_draft este folosit pentru afișarea în GUI.
            # email_subject și email_body sunt folosite de sender.
            return {
                "email_subject": subject,
                "email_body": body,
                "email_draft": (
                    f"Subiect: {subject}\n\n"
                    f"{body}"
                ),
                "email_revision_count": 0,
                "error": None,
            }

        except Exception as exc:
            return {
                "email_subject": "",
                "email_body": "",
                "email_draft": "",
                "error": (
                    "EmailWriterAgent nu a putut redacta emailul: "
                    f"{exc}"
                ),
            }