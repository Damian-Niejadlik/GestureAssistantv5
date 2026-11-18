import json
import time

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QCheckBox, QComboBox, QLabel, QPushButton, QVBoxLayout, QWidget

from src.gesture_assistant.gestures.definitions import GestureConfig, Quality
from src.gesture_assistant.gestures.personal import SINGLE, features, valid
from src.gesture_assistant.gestures.quality import inspect_hand
from src.gesture_assistant.ui.camera_view import CameraView
from src.gesture_assistant.ui.display_names import GESTURES


class CalibrationPage(QWidget):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.settings = QSettings("GestureAssistant", "GestureAssistant")
        self.pending = []
        self.last = None
        self.capture_session = False
        layout = QVBoxLayout(self)
        title = QLabel("Kalibracja gestów")
        title.setProperty("role", "title")
        layout.addWidget(title)
        self.enabled = self.option(layout, "Używaj mojej kalibracji", "enabled")
        self.mirror = self.option(layout, "Odbicie lustrzane", "mirror")
        self.rotate = self.option(layout, "Obrót kamery o 180°", "rotate")
        self.mirror.hide()
        self.rotate.hide()
        hint = QLabel("Ustawienia obowiązują od następnej sesji kamery. Wybierz gest i zapisz "
                      "10 osobnych próbek. Rozłóż je na co najmniej 3 obszary obrazu. "
                      "Między próbkami opuść dłoń. Kalibracja nie wykonuje akcji.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.gesture = QComboBox()
        for gesture in SINGLE:
            self.gesture.addItem(GESTURES[gesture.value][0], gesture.value)
        self.gesture.currentIndexChanged.connect(self.reset_pending)
        layout.addWidget(self.gesture)
        self.preview = CameraView()
        layout.addWidget(self.preview, 1)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        for text, callback in (("Uruchom kamerę do kalibracji", self.start),
                               ("Zapisz pokazaną próbkę", self.capture),
                               ("Zakończ podgląd kalibracji", self.stop)):
            button = QPushButton(text)
            button.clicked.connect(callback)
            layout.addWidget(button)
        self.reset_pending()

    def option(self, layout, text, key):
        control = QCheckBox(text)
        control.setChecked(self.settings.value(key, False, type=bool))
        control.toggled.connect(lambda checked: self.settings.setValue(key, checked))
        layout.addWidget(control)
        return control

    def orientation(self):
        return self.mirror.isChecked(), self.rotate.isChecked()

    def key(self, source, orientation):
        return f"samples/{source}-{int(orientation[0])}-{int(orientation[1])}"

    def load(self, source, orientation):
        try:
            data = json.loads(self.settings.value(self.key(source, orientation), "{}", type=str))
        except (ValueError, TypeError):
            return {}
        if not isinstance(data, dict):
            return {}
        return {g.value: rows for g in SINGLE if isinstance(rows := data.get(g.value), list)
                and len(rows) == 10 and all(valid(row) for row in rows)}

    def reset_pending(self):
        self.pending.clear()
        self.status.setText(GESTURES[self.gesture.currentData()][1] + " · 0/10 próbek")

    def start(self):
        if self.window._worker is not None or self.window._runtime.is_running:
            self.status.setText("Najpierw zakończ bieżącą sesję w Treningu.")
            return
        self.reset_pending()
        self.source = self.window._camera_index.value()
        self.session_orientation = self.orientation()
        self.capture_session = True
        self.released = True
        self.last = None
        self.window._demo = True
        self.window._start_analysis()
        if self.window._worker is None:
            self.capture_session = self.window._demo = False
            self.status.setText(self.window._error_label.text() or "Nie uruchomiono kamery.")

    def stop(self):
        if self.capture_session:
            self.window._stop_analysis()

    def finished(self):
        if self.capture_session:
            self.capture_session = False
            self.preview.clear()
            self.last = None
            if self.window._failed:
                self.status.setText(self.window._error_label.text())

    def observe(self, frame, result):
        if not self.capture_session:
            return
        height, width = frame.shape[:2]
        hands = tuple(hand for hand in result.hands if len(hand.landmarks) == 21)
        if self.isVisible():
            self.preview.set_frame(frame, hands)
        if not result.hands:
            self.released = True
        self.last = (time.monotonic(), result.hands, width, height)

    def capture(self):
        if not self.capture_session or self.last is None:
            self.status.setText("Najpierw uruchom podgląd kalibracji.")
            return
        if not self.released:
            self.status.setText(f"Opuść dłoń przed następną próbką · {len(self.pending)}/10")
            return
        seen, hands, width, height = self.last
        if (time.monotonic() - seen > 0.25 or len(hands) != 1
                or inspect_hand(hands[0], width, height, GestureConfig())[0] != Quality.VALID):
            self.status.setText("Pokaż jedną całą dłoń i spróbuj ponownie.")
            return
        vector = features(hands[0], width, height)
        if vector is None:
            self.status.setText("Nie można zapisać tej próbki.")
            return
        wrist = hands[0].landmarks[0]
        area = (int(wrist.x * 3), int(wrist.y * 3))
        if len(self.pending) == 9 and len({zone for _, zone in self.pending} | {area}) < 3:
            self.status.setText("9/10 — ostatnią próbkę pokaż w innym obszarze obrazu.")
            return
        self.pending.append((vector, area))
        self.released = False
        if len(self.pending) == 10:
            samples = self.load(self.source, self.session_orientation)
            samples[self.gesture.currentData()] = [values for values, _ in self.pending]
            self.settings.setValue(self.key(self.source, self.session_orientation), json.dumps(samples))
            self.settings.sync()
            self.pending.clear()
            if self.settings.status() == QSettings.Status.NoError:
                self.status.setText("Zapisano 10 próbek. Włącz kalibrację i rozpocznij nową sesję.")
            else:
                self.status.setText("Nie udało się zapisać próbek w ustawieniach systemu.")
        else:
            self.status.setText(f"{len(self.pending)}/10 · opuść dłoń i zmień położenie w kadrze")

