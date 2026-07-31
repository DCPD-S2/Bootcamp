from __future__ import annotations

from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field

from agents.base_agent import BaseAgent
from assistant.state import AssistantState


class RevisedEmail(BaseModel):
    subject: str = Field(
        description=(
            "Subiectul corectat al emailului, "
            "fără prefixul «Subiect:»."
        )
    )

    body: str = Field(
        description=(
            "Corpul complet și corectat al emailului, "
            "fără subiect."
        )
    )


class EmailReviserAgent(BaseAgent):
    def __init__(
        self,
        model: str = "llama3.1:8b",
    ) -> None:
        llm = ChatOllama(
            model=model,
            temperature=0.2,
        )

        # Modelul trebuie să întoarcă separat
        # subiectul și corpul emailului corectat.
        self.reviser = llm.with_structured_output(
            RevisedEmail
        )

    def execute(
        self,
        state: AssistantState,
    ) -> dict[str, object]:
        try:
            current_subject = str(
                state.get("email_subject", "")
            ).strip()

            current_body = str(
                state.get("email_body", "")
            ).strip()

            feedback = str(
                state.get("email_feedback", "")
            ).strip()

            if not current_subject:
                raise ValueError(
                    "Emailul curent nu are subiect."
                )

            if not current_body:
                raise ValueError(
                    "Emailul curent nu are conținut."
                )

            if not feedback:
                raise ValueError(
                    "Nu există feedback pentru corectarea emailului."
                )

            revised_email = self.reviser.invoke([
                (
                    "system",
                    """
                    Corectează emailul folosind feedbackul primit.

                    Returnează separat:
                    - subject: subiectul corectat;
                    - body: corpul corectat al emailului.

                    Reguli:
                    - respectă cererea inițială;
                    - aplică feedbackul primit;
                    - păstrează informațiile corecte;
                    - nu inventa informații;
                    - respectă limba și tonul cerut;
                    - nu include prefixul „Subiect:” în subject;
                    - nu include subiectul în body;
                    - nu adăuga explicații în afara emailului.
                    """.strip(),
                ),
                (
                    "human",
                    f"""
                    Cererea inițială:
                    {state["user_message"]}

                    Subiectul curent:
                    {current_subject}

                    Corpul curent:
                    {current_body}

                    Feedbackul reviewerului:
                    {feedback}
                    """.strip(),
                ),
            ])

            if revised_email is None:
                raise ValueError(
                    "Modelul nu a returnat emailul corectat."
                )

            revised_subject = revised_email.subject.strip()
            revised_body = revised_email.body.strip()

            if not revised_subject:
                raise ValueError(
                    "Emailul corectat nu are subiect."
                )

            if not revised_body:
                raise ValueError(
                    "Emailul corectat nu are conținut."
                )

            revision_count = (
                state.get("email_revision_count", 0) + 1
            )

            return {
                "email_subject": revised_subject,
                "email_body": revised_body,
                "email_draft": (
                    f"Subiect: {revised_subject}\n\n"
                    f"{revised_body}"
                ),
                "email_revision_count": revision_count,
                "error": None,
            }

        except Exception as exc:
            return {
                "error": (
                    "EmailReviserAgent nu a putut corecta "
                    f"emailul: {exc}"
                )
            }