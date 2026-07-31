from __future__ import annotations

from pathlib import Path

from faster_whisper import WhisperModel
from PySide6.QtCore import QObject, Signal, Slot


class TranscriptionWorker(QObject):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        audio_path: str | Path,
        model_name: str = "small",
    ) -> None:
        super().__init__()

        self.audio_path = Path(audio_path)
        self.model_name = model_name

    @Slot()
    def run(self) -> None:
        try:
            if not self.audio_path.exists():
                raise FileNotFoundError(
                    f"Fișierul audio nu există: {self.audio_path}"
                )

            model = WhisperModel(
                self.model_name,
                device="cpu",
                compute_type="int8",
            )

            segments, _ = model.transcribe(
                str(self.audio_path),
                language="ro",
                vad_filter=True,
                beam_size=5,
            )

            text = " ".join(
                segment.text.strip()
                for segment in segments
                if segment.text.strip()
            ).strip()

            if not text:
                raise ValueError(
                    "Nu am detectat vorbire în înregistrare."
                )

            self.finished.emit(text)

        except Exception as exc:
            self.failed.emit(str(exc))