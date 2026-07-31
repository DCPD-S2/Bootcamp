from __future__ import annotations

import re

from agents.base_agent import BaseAgent
from assistant.state import AssistantState
from tools.email_sender_tools import EmailSenderTools


class EmailSenderAgent(BaseAgent):
    def execute(
        self,
        state: AssistantState,
    ) -> dict[str, object]:
        try:
            user_message = str(
                state.get("user_message", "")
            ).strip()

            # Caută adresa destinatarului în mesajul utilizatorului.
            email_match = re.search(
                r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b",
                user_message,
            )

            # Dacă adresa apare în mesaj, o folosim.
            # Altfel încercăm valoarea păstrată în stare.
            if email_match:
                recipient = email_match.group(0).strip()
            else:
                recipient = str(
                    state.get("email_to") or ""
                ).strip()

            # Aceste valori sunt generate de EmailWriterAgent
            # și eventual actualizate de EmailReviserAgent.
            subject = str(
                state.get("email_subject") or ""
            ).strip()

            body = str(
                state.get("email_body") or ""
            ).strip()

            if not recipient:
                raise ValueError(
                    "Nu ai specificat adresa destinatarului."
                )

            if not subject:
                raise ValueError(
                    "Nu există un email pregătit pentru trimitere."
                )

            if not body:
                raise ValueError(
                    "Emailul pregătit nu are conținut."
                )

            # Trimite emailul real prin SMTP.
            EmailSenderTools.send_email(
                recipient=recipient,
                subject=subject,
                body=body,
            )

            return {
                "email_to": recipient,
                "email_sent": True,
                "response": (
                    "Emailul a fost trimis cu succes către "
                    f"{recipient}."
                ),
                "error": None,
            }

        except Exception as exc:
            return {
                "email_sent": False,
                "response": "",
                "error": (
                    "EmailSenderAgent nu a putut trimite emailul: "
                    f"{exc}"
                ),
            }