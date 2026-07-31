from __future__ import annotations
# DDGS este clasa folosită pentru căutări web.
from ddgs import DDGS


class SearchTools:
    # Caută pe internet după textul primit în query.
    @staticmethod
    def search(
        query: str,
        maximum_results: int = 5,
    ) -> list[dict]:
        # Creează o instanță DDGS.
        with DDGS() as ddgs:
            return list(
                ddgs.text(
                    query,
                    max_results=maximum_results,
                )
            )

    @staticmethod
    def build_context(
        results: list[dict],
    ) -> str:
        #Aici se vor adăuga, pe rând, rezultatele formatate.
        context = []

        for index, result in enumerate(results, start=1):
            title = result.get("title", "")
            body = result.get("body", "")
            href = result.get("href", "")
            # Construiește un bloc text pentru rezultatul curent și îl adaugă în lista context.
            context.append(
                f"""
                Rezultat {index}

                Titlu:
                {title}

                Conținut:
                {body}

                Sursă:
                {href}
                """.strip()
            )

        return "\n\n".join(context)