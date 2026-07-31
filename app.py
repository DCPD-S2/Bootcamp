from __future__ import annotations
from assistant.assistant_graph import LocalAssistantGraph


def main() -> None:
    assistant = LocalAssistantGraph(
        model="llama3.1:8b"
    )

    print("Local AI Assistant")
    print("Scrie «exit» pentru închidere.\n")

    while True:
        try:
            user_message = input("Tu: ").strip()

            if user_message.lower() in {
                "exit",
                "quit",
                "ieșire",
                "iesire",
            }:
                break

            if not user_message:
                continue

            route = assistant.inspect_route(user_message)
            print(f"[Agent selectat: {route}]")
            answer = assistant.invoke(user_message)
            print(f"AI: {answer}\n")

        except KeyboardInterrupt:
            break

        except Exception as exc:
            print(f"Eroare: {exc}\n")


if __name__ == "__main__":
    main()