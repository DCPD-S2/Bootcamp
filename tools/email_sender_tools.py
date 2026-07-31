from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


class EmailSenderTools:
    @staticmethod
    def send_email(
        recipient: str,
        subject: str,
        body: str,
    ) -> None:
        smtp_host = os.getenv("SMTP_HOST")
        smtp_port = int(
            os.getenv("SMTP_PORT", "587")
        )
        smtp_user = os.getenv("SMTP_USER")
        smtp_password = os.getenv("SMTP_PASSWORD")
        smtp_sender = os.getenv(
            "SMTP_SENDER",
            smtp_user,
        )

        if not smtp_host:
            raise ValueError(
                "SMTP_HOST nu este configurat."
            )

        if not smtp_user:
            raise ValueError(
                "SMTP_USER nu este configurat."
            )

        if not smtp_password:
            raise ValueError(
                "SMTP_PASSWORD nu este configurat."
            )

        if not smtp_sender:
            raise ValueError(
                "SMTP_SENDER nu este configurat."
            )

        message = EmailMessage()
        message["From"] = smtp_sender
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)

        with smtplib.SMTP(
            smtp_host,
            smtp_port,
            timeout=20,
        ) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()

            server.login(
                smtp_user,
                smtp_password,
            )

            server.send_message(message)