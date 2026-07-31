from __future__ import annotations
from typing import Literal, TypedDict

# Lista tuturor agenților disponibili în aplicație.
AgentName = Literal[ # Literal restricționează valorile permise doar la aceste șiruri.
    "conversation",
    "search",
    "weather",
    "system",
    "calculator",
    "email",
  
]

# Starea aplicației care este transmisă între nodurile LangGraph.
class AssistantState(TypedDict, total=False):
    # total=False înseamnă că toate câmpurile sunt opționale.
    # La început poate exista doar mesajul utilizatorului, iar pe parcurs se completează și celelalte câmpuri.
    user_message: str
    selected_agent: AgentName
    response: str
    error: str | None
    
    # Câmpuri folosite doar pe fluxul de email.
    email_draft: str
    email_subject: str
    email_body: str

    email_feedback: str
    email_approved: bool
    email_revision_count: int

    email_to: str | None
    email_sent: bool
    