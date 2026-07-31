from __future__ import annotations
import requests


class WeatherTools:
    # API folosit pentru transformarea numelui orașului în coordonate geografice.
    GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
    # API folosit pentru obținerea datelor meteo.
    WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
    # Open-Meteo întoarce coduri numerice pentru starea vremii.
    # Dicționarul le transformă în texte ușor de înțeles.
    WEATHER_CODES = {
        0: "cer senin",
        1: "cer în mare parte senin",
        2: "cer parțial noros",
        3: "cer noros",
        45: "ceață",
        48: "ceață cu depunere de chiciură",
        51: "burniță slabă",
        53: "burniță moderată",
        55: "burniță puternică",
        61: "ploaie slabă",
        63: "ploaie moderată",
        65: "ploaie puternică",
        71: "ninsoare slabă",
        73: "ninsoare moderată",
        75: "ninsoare puternică",
        80: "averse slabe",
        81: "averse moderate",
        82: "averse puternice",
        95: "furtună",
        96: "furtună cu grindină slabă",
        99: "furtună cu grindină puternică",
    }

    @classmethod
    def _get_coordinates(
        cls,
        city: str | None,
    ) -> tuple[str, float, float]:
        if city is None or not city.strip():
            raise ValueError("Nu ai specificat orașul.")
        # Trimite o cerere GET către API-ul de geocodare.
        response = requests.get(
            cls.GEOCODING_URL,
            params={
                "name": city.strip(),
                "count": 1,
                "language": "ro",
                "format": "json",
            },
            timeout=10,
        )
        response.raise_for_status()

        data = response.json()
        results = data.get("results", [])

        if not results:
            raise ValueError(
                f"Nu am găsit orașul «{city}»."
            )

        result = results[0]

        city_name = result.get("name", city)
        country = result.get("country", "")

        location_name = city_name
        if country:
            location_name = f"{city_name}, {country}"

        return (
            location_name,
            float(result["latitude"]),
            float(result["longitude"]),
        )

    @classmethod
    def get_weather(
        cls,
        city: str | None,
    ) -> str:
        # Transformă numele orașului în coordonate.
        location, latitude, longitude = (
            cls._get_coordinates(city)
        )
        # Trimite cererea către API-ul meteo.
        response = requests.get(
            cls.WEATHER_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                # Datele meteo actuale solicitate.
                "current": (
                    "temperature_2m,"
                    "apparent_temperature,"
                    "relative_humidity_2m,"
                    "weather_code,"
                    "wind_speed_10m"
                ),
                "timezone": "auto",
            },
            timeout=10,
        )
        response.raise_for_status()

        current = response.json().get("current")

        if not current:
            raise ValueError(
                "Serviciul meteo nu a returnat date curente."
            )
        # Codul numeric al stării vremii.
        code = current.get("weather_code")
        # Transformă codul într-o descriere text.
        description = cls.WEATHER_CODES.get(
            code,
            "condiții meteo necunoscute",
        )

        temperature = current.get("temperature_2m")
        apparent = current.get("apparent_temperature")
        humidity = current.get("relative_humidity_2m")
        wind = current.get("wind_speed_10m")

        return (
            f"În {location} sunt {temperature}°C, "
            f"cu {description}. "
            f"Temperatura resimțită este {apparent}°C, "
            f"umiditatea este {humidity}%, "
            f"iar vântul are {wind} km/h."
        )

    @classmethod
    def get_forecast(
        cls,
        city: str | None,
        days_ahead: int = 1,
    ) -> str:
        if days_ahead < 0:
            raise ValueError(
                "Numărul de zile nu poate fi negativ."
            )

        location, latitude, longitude = (
            cls._get_coordinates(city)
        )

        # Cerem suficiente zile pentru a include ziua dorită.
        forecast_days = days_ahead + 1

        response = requests.get(
            cls.WEATHER_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "daily": (
                    "weather_code,"
                    "temperature_2m_max,"
                    "temperature_2m_min,"
                    "precipitation_probability_max"
                ),
                "forecast_days": forecast_days,
                "timezone": "auto",
            },
            timeout=10,
        )

        response.raise_for_status()

        daily = response.json().get("daily")

        if not daily:
            raise ValueError(
                "Serviciul meteo nu a returnat prognoza."
            )

        dates = daily.get("time", [])
        codes = daily.get("weather_code", [])
        maximums = daily.get("temperature_2m_max", [])
        minimums = daily.get("temperature_2m_min", [])
        precipitation = daily.get(
            "precipitation_probability_max",
            [],
        )

        if days_ahead >= len(dates):
            raise ValueError(
                "Prognoza nu este disponibilă pentru ziua solicitată."
            )

        date = dates[days_ahead]
        code = codes[days_ahead]
        maximum = maximums[days_ahead]
        minimum = minimums[days_ahead]
        precipitation_probability = precipitation[days_ahead]

        description = cls.WEATHER_CODES.get(
            code,
            "condiții necunoscute",
        )

        if days_ahead == 0:
            day_label = "Astăzi"
        elif days_ahead == 1:
            day_label = "Mâine"
        elif days_ahead == 2:
            day_label = "Poimâine"
        else:
            day_label = f"Peste {days_ahead} zile"

        return (
            f"{day_label}, în {location}, va fi "
            f"{description}. "
            f"Temperatura minimă va fi {minimum}°C, "
            f"iar maxima {maximum}°C. "
            f"Probabilitatea de precipitații este "
            f"{precipitation_probability}%. "
            f"Data prognozei: {date}."
        )