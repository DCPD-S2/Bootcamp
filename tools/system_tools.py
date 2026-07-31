from __future__ import annotations

from datetime import datetime
import psutil # Bibliotecă Python pentru acces la informațiile sistemului de operare.
import platform

class SystemTools:
    @staticmethod
    def get_time() -> str:
        now = datetime.now()
        return f"Este ora {now:%H:%M}."

    @staticmethod
    def get_date() -> str:
        now = datetime.now()
        return f"Data curentă este {now:%d.%m.%Y}."

    @staticmethod
    def get_datetime() -> str:
        now = datetime.now()
        return (
            f"Este {now:%d.%m.%Y}, ora {now:%H:%M}."
        )

    @staticmethod
    def get_ram() -> str:
        memory = psutil.virtual_memory()

        total = memory.total / (1024**3)
        available = memory.available / (1024**3)

        return (
            f"Ai {total:.1f} GB RAM, "
            f"dintre care {available:.1f} GB disponibili."
        )

    @staticmethod
    def get_cpu() -> str:
        return platform.processor()

    @staticmethod
    def get_battery() -> str:
        battery = psutil.sensors_battery()

        if battery is None:
            return "Acest calculator nu are baterie sau informațiile despre baterie nu sunt disponibile."

        percent = battery.percent
        plugged = battery.power_plugged

        if plugged:
            status = "se încarcă"
        else:
            status = "funcționează pe baterie"

        if battery.secsleft in (
            psutil.POWER_TIME_UNKNOWN,
            psutil.POWER_TIME_UNLIMITED,
        ):
            time_left = "necunoscut"
        else:
            hours = battery.secsleft // 3600
            minutes = (battery.secsleft % 3600) // 60
            time_left = f"{hours}h {minutes}min"

        return (
            f"Bateria este la {percent:.0f}% și {status}. "
            f"Timp estimat rămas: {time_left}."
        )