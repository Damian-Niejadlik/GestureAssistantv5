import re

from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QColorDialog, QComboBox, QFormLayout, QLabel, QPushButton, QWidget

from src.gesture_assistant.ui import tokens
from src.gesture_assistant.ui.theme import get_stylesheet


def contrast(first, second):
    def luminance(value):
        rgb = [int(value[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in rgb]
        return sum(x * y for x, y in zip(linear, (0.2126, 0.7152, 0.0722), strict=True))
    a, b = sorted((luminance(first), luminance(second)))
    return (b + 0.05) / (a + 0.05)


class AppearancePage(QWidget):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.settings = QSettings("GestureAssistant", "GestureAssistant")
        layout = QFormLayout(self)
        self.mode = QComboBox()
        self.mode.addItem("Ciemny", "dark")
        self.mode.addItem("Jasny", "light")
        current = self.settings.value("appearance/mode", "dark", type=str)
        self.mode.setCurrentIndex(max(0, self.mode.findData(current)))
        layout.addRow("Motyw", self.mode)
        self.colors = {}
        for key, title in (("ACCENT", "Główny kolor akcentu"), ("MAGENTA", "Kolor wyboru i fokusu")):
            button = QPushButton()
            button.clicked.connect(lambda checked=False, k=key: self.pick(k))
            layout.addRow(title, button)
            self.colors[key] = button
        self.note = QLabel("Zmiany wyglądu nie zmieniają profili ani działania gestów.")
        self.note.setWordWrap(True)
        layout.addRow(self.note)
        reset = QPushButton("Przywróć domyślne kolory tego motywu")
        reset.clicked.connect(self.reset)
        layout.addRow(reset)
        self.mode.currentIndexChanged.connect(self.apply)
        self.apply()

    def palette_values(self):
        mode = self.mode.currentData()
        colors = dict(tokens.LIGHT if mode == "light" else tokens.DARK)
        for key in self.colors:
            saved = self.settings.value(f"appearance/{mode}/{key}", "", type=str)
            if re.fullmatch(r"#[0-9a-fA-F]{6}", saved) and self.readable(saved, colors):
                colors[key] = saved
        return colors

    @staticmethod
    def readable(value, colors):
        return all(contrast(value, colors[key]) >= 4.5 for key in ("RAISED", "SURFACE"))

    def pick(self, key):
        colors = self.palette_values()
        color = QColorDialog.getColor(QColor(colors[key]), self, "Wybierz kolor akcentu")
        if not color.isValid():
            return
        if not self.readable(color.name(), colors):
            self.note.setText("Wybierz bardziej kontrastowy kolor dla tego motywu.")
            return
        self.settings.setValue(f"appearance/{self.mode.currentData()}/{key}", color.name())
        self.apply()

    def reset(self):
        for key in self.colors:
            self.settings.remove(f"appearance/{self.mode.currentData()}/{key}")
        self.apply()

    def apply(self, _index=None):
        self.settings.setValue("appearance/mode", self.mode.currentData())
        colors = self.palette_values()
        for key, value in colors.items():
            setattr(tokens, key, value)
        tokens.ON_ACCENT = max(("#000000", "#FFFFFF"), key=lambda c: contrast(c, tokens.ACCENT))
        palette = QPalette(self.window.palette())
        for role, key in ((QPalette.ColorRole.Window, "BACKGROUND"),
                          (QPalette.ColorRole.Base, "SURFACE"),
                          (QPalette.ColorRole.AlternateBase, "RAISED"),
                          (QPalette.ColorRole.WindowText, "TEXT"),
                          (QPalette.ColorRole.Text, "TEXT"),
                          (QPalette.ColorRole.Button, "RAISED"),
                          (QPalette.ColorRole.ButtonText, "TEXT"),
                          (QPalette.ColorRole.Highlight, "ACCENT"),
                          (QPalette.ColorRole.HighlightedText, "ON_ACCENT")):
            palette.setColor(role, QColor(getattr(tokens, key)))
        self.window.setPalette(palette)
        self.window.setStyleSheet(get_stylesheet())
        for key, button in self.colors.items():
            button.setText(colors[key].upper())
        self.note.setText("Wygląd zapisany dla bieżącego użytkownika.")
        self.window.update()
