from __future__ import annotations
import sys
from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow
from dotenv import load_dotenv

load_dotenv()

def main() -> None:
    application = QApplication(sys.argv)

    application.setApplicationName(
        "Local AI Assistant"
    )

    window = MainWindow()
    window.show()

    sys.exit(application.exec())


if __name__ == "__main__":
    main()