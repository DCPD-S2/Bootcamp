from __future__ import annotations

import re

#Transformă textul afișat într-o variantă mai naturală pentru sintetizarea vocală.
class SpeechTools:
    @staticmethod
    def prepare_for_tts(text: str) -> str:

        # 25.5 -> 25 virgulă 5
        text = re.sub(
            r"(?<!\w)(-?\d+)\.(\d+)(?!\w)",
            r"\1 virgulă \2",
            text,
        )

        # 25,5 -> 25 virgulă 5
        text = re.sub(
            r"(?<!\w)(-?\d+),(\d+)(?!\w)",
            r"\1 virgulă \2",
            text,
        )

        # 25°C sau 25 °C -> 25 grade Celsius
        text = re.sub(
            r"(-?\d+(?:[.,]\d+)?)\s*°\s*C",
            r"\1 grade Celsius",
            text,
            flags=re.IGNORECASE,
        )

        # 25% -> 25 la sută
        text = re.sub(
            r"(-?\d+(?:[.,]\d+)?)\s*%",
            r"\1 la sută",
            text,
        )

        # km/h -> kilometri pe oră
        text = re.sub(
            r"\bkm/h\b",
            "kilometri pe oră",
            text,
            flags=re.IGNORECASE,
        )

        # GB -> gigabaiți
        text = re.sub(
            r"\bGB\b",
            "gigabaiți",
            text,
        )

        # MB -> megabaiți
        text = re.sub(
            r"\bMB\b",
            "megabaiți",
            text,
        )

        return text