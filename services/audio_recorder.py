from __future__ import annotations

import tempfile
import threading
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd


class AudioRecorder:
    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels

        self._frames: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()

    @property
    def is_recording(self) -> bool:
        return self._stream is not None

    def start(self) -> None:
        if self.is_recording:
            return

        with self._lock:
            self._frames.clear()

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="int16",
            callback=self._audio_callback,
        )

        self._stream.start()

    def stop(self) -> Path:
        if self._stream is None:
            raise RuntimeError(
                "Înregistrarea nu este pornită."
            )

        self._stream.stop()
        self._stream.close()
        self._stream = None

        with self._lock:
            if not self._frames:
                raise ValueError(
                    "Nu a fost înregistrat niciun sunet."
                )

            audio = np.concatenate(
                self._frames,
                axis=0,
            )

        temporary_file = tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False,
        )
        temporary_file.close()

        audio_path = Path(temporary_file.name)

        with wave.open(str(audio_path), "wb") as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio.tobytes())

        return audio_path

    def cancel(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        with self._lock:
            self._frames.clear()

    def _audio_callback(
        self,
        input_data: np.ndarray,
        frames: int,
        time_info,
        status,
    ) -> None:
        del frames, time_info

        if status:
            print(f"Audio status: {status}")

        with self._lock:
            self._frames.append(input_data.copy())