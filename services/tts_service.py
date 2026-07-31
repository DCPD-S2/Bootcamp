from __future__ import annotations

import tempfile
import threading
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd
from piper import PiperVoice


class TTSService:
    def __init__(
        self,
        model_path: str | Path,
    ) -> None:
        self.model_path = Path(model_path)

        self.config_path = Path(
            f"{self.model_path}.json"
        )

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Modelul Piper nu există: {self.model_path}"
            )

        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Configurația Piper nu există: "
                f"{self.config_path}"
            )

        self.voice = PiperVoice.load(
            str(self.model_path),
            config_path=str(self.config_path),
        )

        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    @property
    def is_speaking(self) -> bool:
        return (
            self._thread is not None
            and self._thread.is_alive()
        )

    def speak(self, text: str) -> None:
        clean_text = text.strip()

        if not clean_text:
            return

        self.stop()

        self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._synthesize_and_play,
            args=(clean_text,),
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        sd.stop()

    def _synthesize_and_play(self, text: str) -> None:
        temporary_file = tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False,
        )
        temporary_file.close()

        wav_path = Path(temporary_file.name)

        try:
            with wave.open(str(wav_path), "wb") as wav_file:
                self.voice.synthesize_wav(
                    text,
                    wav_file,
                )

            if self._stop_event.is_set():
                return

            with wave.open(str(wav_path), "rb") as wav_file:
                sample_rate = wav_file.getframerate()
                channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
                frames = wav_file.readframes(
                    wav_file.getnframes()
                )

            if sample_width != 2:
                raise ValueError(
                    "Format audio Piper neașteptat."
                )

            audio = np.frombuffer(
                frames,
                dtype=np.int16,
            )

            if channels > 1:
                audio = audio.reshape(-1, channels)

            if self._stop_event.is_set():
                return

            sd.play(
                audio,
                samplerate=sample_rate,
            )
            sd.wait()

        except Exception as exc:
            print(f"Eroare Piper: {exc}")

        finally:
            try:
                wav_path.unlink(missing_ok=True)
            except OSError:
                pass