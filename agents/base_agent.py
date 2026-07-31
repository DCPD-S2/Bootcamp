from __future__ import annotations
from abc import ABC, abstractmethod
from assistant.state import AssistantState

# Clasă de bază pentru toți agenții asistentului.
class BaseAgent(ABC):
    @abstractmethod #Orice clasă care moștenește BaseAgent este obligată să implementeze propria metodă execute().
    def execute(
        self,
        state: AssistantState,  # Primește starea curentă a asistentului
    ) -> dict[str, str | None]:
        """Procesează starea și returnează actualizările."""
     #  returnează câmpurile care trebuie actualizate în AssistantState.