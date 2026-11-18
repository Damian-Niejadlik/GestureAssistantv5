import argparse
import sys

from PySide6.QtWidgets import QApplication

from src.gesture_assistant.ui.main_window import MainWindow


def main() -> int:
    parser = argparse.ArgumentParser(description="GestureAssistant")
    parser.add_argument("--config", default=None, help="Opcjonalny lokalny plik ustawień JSON")
    parser.add_argument("--demo", action="store_true", help="Podgląd bez wykonywania akcji")
    args, qt_args = parser.parse_known_args()
    application = QApplication([sys.argv[0], *qt_args])
    window = MainWindow(config_path=args.config)
    window.show()
    if args.demo:
        window._workspace.open_demo()
    return application.exec()

