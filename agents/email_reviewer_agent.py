from __future__ import annotations

from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field

from agents.base_agent import BaseAgent
from assistant.state import AssistantState


class EmailReview(BaseModel):
    approved: bool = Field(
        description=(
            "True dacă emailul respectă complet cererea "
            "și poate fi folosit fără modificări."
        )
    )

    feedback: str = Field(
        description=(
            "Modificările concrete necesare. "
            "Șir gol dacă emailul este aprobat."
        )
    )


class EmailReviewerAgent(BaseAgent):
    def __init__(
        self,
        model: str = "llama3.1:8b",
    ) -> None:
        llm = ChatOllama(
            model=model,
            temperature=0,
        )

        self.reviewer = llm.with_structured_output(
            EmailReview
        )

    def execute(
        self,
        state: AssistantState,
    ) -> dict[str, object]:
        try:
            subject = str(
                state.get("email_subject", "")
            ).strip()

            body = str(
                state.get("email_body", "")
            ).strip()

            if not subject:
                raise ValueError(
                    "Emailul nu are subiect."
                )

            if not body:
                raise ValueError(
                    "Emailul nu are conținut."
                )

            review = self.reviewer.invoke([
                (
                    "system",
                    """
                    Verifică emailul redactat.

                    Aprobă-l doar dacă:
                    - respectă cererea utilizatorului;
                    - subiectul este clar și relevant;
                    - corpul emailului are tonul potrivit;
                    - este clar și politicos;
                    - nu inventează informații;
                    - nu conține explicații inutile;
                    - are formulă de adresare și încheiere;
                    - nu conține subiectul repetat în corp.

                    Dacă nu este bun:
                    - approved trebuie să fie false;
                    - feedback trebuie să fie concret și aplicabil.

                    Dacă este bun:
                    - approved trebuie să fie true;
                    - feedback trebuie să fie șir gol.
                    """.strip(),
                ),
                (
                    "human",
                    f"""
                    Cererea utilizatorului:
                    {state["user_message"]}

                    Subiect:
                    {subject}

                    Corpul emailului:
                    {body}
                    """.strip(),
                ),
            ])

            if review is None:
                raise ValueError(
                    "Nu am putut verifica emailul."
                )

            feedback = review.feedback.strip()

            if review.approved:
                feedback = ""

            return {
                "email_approved": review.approved,
                "email_feedback": feedback,
                "error": None,
            }

        except Exception as exc:
            return {
                "email_approved": False,
                "email_feedback": "",
                "error": (
                    "EmailReviewerAgent nu a putut verifica "
                    f"emailul: {exc}"
                ),
            }