from __future__ import annotations
from PySide6.QtCore import QObject, QThread, Signal, Slot

class AssistantWorker(QObject):
    finished = Signal(str, int)
    failed = Signal(str, int)

    # Trimite către GUI:
    # - numele nodului;
    # - starea lui: active sau completed.
    progress = Signal(str, str)

    def __init__(
        self,
        assistant,
        message: str,
        request_id: int,
    ) -> None:
        super().__init__()

        self.assistant = assistant
        self.message = message
        self.request_id = request_id

    @Slot()
    def run(self) -> None:
        try:
            final_response = ""

            for event in self.assistant.stream(
                self.message
            ):
                if not isinstance(event, dict):
                    continue

                # Uneori un eveniment poate conține
                # mai mult de un nod.
                for node_name, update in event.items():
                    self.progress.emit(
                        node_name,
                        "active",
                    )

                    QThread.msleep(300)

                    if isinstance(update, dict):
                        error = update.get("error")

                        if error:
                            raise RuntimeError(str(error))

                        response = update.get("response")

                        if response:
                            final_response = str(response)

                    self.progress.emit(
                        node_name,
                        "completed",
                    )

            if not final_response.strip():
                raise RuntimeError(
                    "Graful nu a returnat niciun răspuns."
                )

            self.finished.emit(
                final_response.strip(),
                self.request_id,
            )

        except Exception as exc:
            self.failed.emit(
                str(exc),
                self.request_id,
            )