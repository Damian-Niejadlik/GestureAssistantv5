import csv
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QListWidget, QMenu, QMessageBox, QPushButton, QScrollArea,
    QSpinBox, QStackedWidget, QSystemTrayIcon, QTabWidget, QVBoxLayout, QWidget,
)

from src.gesture_assistant.ui import tokens
from src.gesture_assistant.ui.appearance import AppearancePage
from src.gesture_assistant.ui.calibration import CalibrationPage
from src.gesture_assistant.ui.display_names import PROFILES, action_name

from copy import deepcopy


def label(text, role="secondary"):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(True)
    widget.setProperty("role", role)
    return widget


def card():
    frame = QFrame()
    frame.setProperty("role", "card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(tokens.SPACE)
    return frame, layout


def scroll(widget):
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setWidget(widget)
    return area


def app_icon():
    image = QPixmap(32, 32)
    image.fill(QColor(tokens.BACKGROUND))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(tokens.ACCENT), 2))
    painter.drawRoundedRect(4, 4, 24, 24, 6, 6)
    painter.drawLine(9, 19, 14, 12)
    painter.drawLine(14, 12, 19, 21)
    painter.drawLine(19, 21, 23, 14)
    painter.end()
    return QIcon(image)


class Workspace(QWidget):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        preview, bindings, parameters = (window._tabs.widget(i) for i in range(3))
        while window._tabs.count():
            window._tabs.removeTab(0)
        self.setObjectName("Workspace")
        layout = QHBoxLayout(self)
        sidebar, nav = card()
        sidebar.setFixedWidth(216)
        layout.setSpacing(16)
        nav.addWidget(label("GestureAssistant", "title"))
        self.pages = QStackedWidget()
        self.nav = []
        for index, text in enumerate(("Start", "Podgląd i sterowanie", "Historia", "Ustawienia", "Kalibracja gestów")):
            button = QPushButton(text)
            button.setCheckable(True)
            button.setProperty("nav", True)
            button.clicked.connect(lambda checked=False, i=index: self.navigate(i))
            nav.addWidget(button)
            self.nav.append(button)
        nav.addStretch()
        self.source = label("Źródło: kamera nieaktywna")
        nav.addWidget(self.source)
        nav.addWidget(label("0.1.0 · Etap 4"))
        help_button = QPushButton("Pomoc")
        help_button.clicked.connect(self.help)
        nav.addWidget(help_button)
        layout.addWidget(sidebar)
        layout.addWidget(self.pages, 1)
        self.pages.addWidget(self._build_dashboard())
        self.pages.addWidget(scroll(preview))
        history, panel = card()
        panel.addWidget(label("Historia sesji", "title"))
        self.filter = QComboBox()
        self.filter.addItems(("Wszystkie wyniki", "Wykonane", "Symulacje", "Odmowy i błędy"))
        self.filter.currentIndexChanged.connect(self.refresh_history)
        panel.addWidget(self.filter)
        self.rows = QListWidget()
        self.rows.currentRowChanged.connect(self.details)
        panel.addWidget(self.rows, 1)
        self.detail = label("Brak zapisanych wyników w tej sesji.")
        panel.addWidget(self.detail)
        controls = QHBoxLayout()
        self.export_button = QPushButton("Eksportuj widoczne do CSV")
        self.export_button.clicked.connect(self.export)
        controls.addWidget(self.export_button)
        self.clear_button = QPushButton("Usuń historię sesji")
        self.clear_button.clicked.connect(self.clear)
        controls.addWidget(self.clear_button)
        panel.addLayout(controls)
        self.pages.addWidget(history)
        self.settings_tabs = QTabWidget()
        self.settings_tabs.setObjectName("SettingsTabs")
        self.settings_tabs.setDocumentMode(True)
        self.settings_tabs.tabBar().setUsesScrollButtons(True)
        self.settings_tabs.tabBar().setExpanding(False)
        self.settings_tabs.addTab(bindings, "Profile akcji")
        self.settings_tabs.addTab(parameters, "Gesty i ruchy")
        self.settings_tabs.addTab(self._build_camera_settings(), "Kamera")
        self.settings_tabs.addTab(self._build_confirmation_settings(),
                                 "Potwierdzenie akcji i bezpieczeństwo")
        container, options = card()
        options.addWidget(label("Ustawienia", "title"))
        self.settings_tabs.addTab(scroll(AppearancePage(window)), "Wygląd")
        options.addWidget(self.settings_tabs, 1)
        self.pages.addWidget(container)
        self.calibration = CalibrationPage(window)
        self.pages.addWidget(scroll(self.calibration))
        self.visible_records = []
        self.navigate(0)
        self.refresh_history()
        self.tray = None
        icon = app_icon()
        window.setWindowIcon(icon)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(icon, window)
            self.tray.setToolTip("GestureAssistant")
            menu = QMenu(window)
            menu.addAction("Pokaż okno", self.show_window)
            menu.addAction("Zakończ sesję", window._stop_analysis)
            menu.addAction("Zamknij aplikację", window.close)
            self.tray.setContextMenu(menu)
            self.tray.activated.connect(self.activate_tray)
            self.tray.show()

    def _build_dashboard(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)
        hero, content = card()
        content.addWidget(label("PANEL STARTOWY"))
        content.addWidget(label("Przygotuj sterowanie gestami", "title"))
        self.dashboard_state = label("", "status")
        content.addWidget(self.dashboard_state)
        buttons = QHBoxLayout()
        for title, handler, primary in (
            ("Przygotuj kamerę", self.prepare, True),
            ("Uruchom demo bez akcji", self.open_demo, False),
        ):
            button = QPushButton(title)
            button.setProperty("primary", primary)
            button.clicked.connect(handler)
            buttons.addWidget(button)
        buttons.addStretch()
        content.addLayout(buttons)
        layout.addWidget(hero)

        profiles, content = card()
        content.addWidget(label("Profil pracy", "title"))
        content.addWidget(label("Wybierz profil bez uruchamiania kamery. "
                                "Zmiana profilu nie włącza sterowania."))
        descriptions = {
            "Auto": "Dobiera profil do aktywnego okna.",
            "Teams": "Mikrofon, kamera i spotkanie.",
            "Browser": "Nawigacja, karty i strony internetowe.",
            "Presentation": "Sterowanie pokazem slajdów.",
            "Media": "Odtwarzanie, utwory i głośność.",
            "System": "Dozwolone czynności systemowe.",
        }
        grid = QGridLayout()
        grid.setSpacing(8)
        self.dashboard_profiles = {}
        for index, (key, description) in enumerate(descriptions.items()):
            frame, tile = card()
            button = QPushButton(PROFILES[key])
            button.setCheckable(True)
            button.setProperty("nav", True)
            button.clicked.connect(lambda checked=False, mode=key: self._choose_profile(mode))
            tile.addWidget(button)
            tile.addWidget(label(description))
            tile.addStretch()
            grid.addWidget(frame, index // 2, index % 2)
            self.dashboard_profiles[key] = button
        content.addLayout(grid)
        layout.addWidget(profiles)

        activity, content = card()
        content.addWidget(label("Ostatnie wykonane akcje", "title"))
        self.recent = label("Brak wykonanych akcji w tej sesji.")
        content.addWidget(self.recent)
        history = QPushButton("Otwórz historię sesji")
        history.clicked.connect(lambda: self.navigate(2))
        content.addWidget(history)
        layout.addWidget(activity)
        layout.addStretch()
        return scroll(page)

    def _choose_profile(self, mode):
        if self.window._demo:
            self.refresh_dashboard()
            return
        combo = self.window._mode_combo
        if self.window._config["mode"] != mode:
            self.window._on_mode_changed(mode)
        previous = combo.blockSignals(True)
        combo.setCurrentIndex(combo.findData(self.window._config["mode"]))
        combo.blockSignals(previous)
        self.refresh_dashboard()

    def refresh_dashboard(self):
        if self.pages.currentIndex() != 0:
            return
        config = self.window._config
        mode = config["mode"]
        if self.window._demo:
            state = "Demo · tylko podgląd"
        elif self.window._worker is None:
            state = "Kamera nieaktywna"
        elif not self.window._runtime.is_running:
            state = "Konsument akcji nieaktywny"
        elif self.window._runtime.safety.paused:
            state = "Akcje wstrzymane"
        elif self.window._runtime.executor.dry_run:
            state = "Symulacja włączona"
        else:
            state = "Sterowanie włączone"
        self.dashboard_state.setText(f"{PROFILES.get(mode, mode)}  ·  {state}")
        for key, button in self.dashboard_profiles.items():
            button.setChecked(key == mode)
            button.setEnabled(not self.window._demo)

    def show_window(self):
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def activate_tray(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_window()

    def help(self):
        QMessageBox.information(self, "Pomoc", "Trening korzysta z prawdziwej kamery. "
                                "Demo nie wykonuje akcji. Do sterowania inną aplikacją "
                                "przełącz fokus na jej okno po wznowieniu akcji.")

    def navigate(self, index):
        self.pages.setCurrentIndex(index)
        for i, button in enumerate(self.nav):
            button.setChecked(i == index)
        if index == 0:
            self.refresh_dashboard()
        if index in (0, 2):
            self.refresh_history()

    def prepare(self):
        if self.window._worker is not None:
            self.navigate(1)
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Przygotowanie sesji")
        form = QFormLayout(dialog)
        profile = QComboBox(dialog)
        source = self.window._mode_combo
        for index in range(source.count()):
            profile.addItem(source.itemText(index))
        profile.setCurrentIndex(source.currentIndex())
        camera = QSpinBox(dialog)
        camera.setRange(self.window._camera_index.minimum(), self.window._camera_index.maximum())
        camera.setValue(self.window._camera_index.value())
        form.addRow("Profil", profile)
        form.addRow("Numer kamery", camera)
        form.addRow(label("Otwórz podgląd i sprawdź, czy widać całą dłoń. Ocena jakości "
                          "jest przybliżona. Akcje pozostaną wstrzymane do ręcznego wznowienia."))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Otwórz podgląd")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Wróć")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            source.setCurrentIndex(profile.currentIndex())
            self.window._camera_index.setValue(camera.value())
            self.navigate(1)
            self.window._start_analysis()


    def _build_camera_settings(self):
        page, layout = card()
        layout.addWidget(label("Kamera i wydajność", "title"))
        layout.addWidget(self.window._camera_settings_group)
        note = label("")
        save = QPushButton("Zapisz ustawienia kamery")
        save.setProperty("primary", True)
        save.clicked.connect(lambda: self._save_camera_settings(note))
        layout.addWidget(save)
        layout.addWidget(note)
        layout.addStretch()
        return scroll(page)

    def _save_camera_settings(self, note):
        if self.window._demo:
            note.setText("Zakończ demo lub kalibrację przed zapisem.")
            return
        config = deepcopy(self.window._config)
        config["camera"] = {key: field.value()
                            for key, field in self.window._camera_fields.items()}
        if self.window._apply_configuration(config):
            self.window._camera_index.setValue(config["camera"]["index"])
            note.setText("Zapisano. Parametry obrazu obowiązują od następnej sesji kamery.")
        else:
            note.setText("Nie zapisano ustawień kamery.")

    def _build_confirmation_settings(self):
        page, layout = card()
        layout.addWidget(label("Potwierdzenie akcji i bezpieczeństwo", "title"))
        layout.addWidget(label("Dopuszczenie akcji wrażliwej nie zastępuje przypisania gestu "
                               "ani jednorazowego potwierdzenia dwoma kciukami."))
        layout.addWidget(self.window._safety_settings_group)
        self._confirmation_notice = label("")
        save = QPushButton("Zapisz ustawienia bezpieczeństwa")
        save.setProperty("primary", True)
        save.clicked.connect(self._save_confirmation_settings)
        layout.addWidget(save)
        layout.addWidget(self._confirmation_notice)
        layout.addStretch()
        return scroll(page)

    def _save_confirmation_settings(self):
        window = self.window
        if window._demo:
            self._confirmation_notice.setText("Zakończ demo lub kalibrację przed zapisem.")
            return
        config = deepcopy(window._config)
        config["safety"]["enabled"] = window._safety_enabled_check.isChecked()
        config["execution"]["dry_run"] = window._dry_run_check.isChecked()
        config["safety"]["sleep_computer"] = window._sleep_check.isChecked()
        allowed = set(config["safety"]["confirmed_destructive"])
        allowed.difference_update(window._destructive_checks)
        allowed.update(key for key, box in window._destructive_checks.items() if box.isChecked())
        config["safety"]["confirmed_destructive"] = sorted(allowed)
        if window._apply_configuration(config):
            self._confirmation_notice.setText("Zapisano. Akcje zostały wstrzymane.")
        else:
            self._confirmation_notice.setText("Nie zapisano ustawień bezpieczeństwa.")

    def open_demo(self):
        if self.window._worker is not None or self.window._runtime.is_running:
            QMessageBox.information(self, "Demo", "Najpierw zakończ bieżącą sesję.")
            return
        self.window._demo = True
        self.navigate(1)
        self.window._start_analysis()
        if self.window._worker is None:
            self.window._demo = False

    def refresh_history(self):
        records = self.window._runtime.history()
        mode = self.filter.currentIndex()
        self.visible_records = [record for record in reversed(records) if (
            mode == 0 or self.category(record[1])[0] == mode
        )]
        self.rows.clear()
        for stamp, outcome in self.visible_records:
            date = datetime.fromtimestamp(stamp).strftime("%H:%M:%S")
            self.rows.addItem(f"{date}  ·  {self.category(outcome)[1]}  ·  {action_name(outcome.action_id, grouped=True)}")
        executed = [action_name(outcome.action_id) for _, outcome in reversed(records) if outcome.executed]
        self.recent.setText("\n".join(executed[:4]) or "Brak wykonanych akcji w tej sesji.")
        self.export_button.setEnabled(bool(self.visible_records))
        self.clear_button.setEnabled(bool(records))
        self.details(-1)

    @staticmethod
    def category(outcome):
        if outcome.executed:
            return 1, "Wykonano"
        if outcome.reason == "dry_run_no_side_effect":
            return 2, "Symulacja"
        return 3, "Odmowa lub błąd"

    def details(self, row):
        if 0 <= row < len(self.visible_records):
            _, outcome = self.visible_records[row]
            self.detail.setText(f"{action_name(outcome.action_id, grouped=True)}\n{self.category(outcome)[1]}"
                                f"\n\nSzczegóły techniczne: {outcome.reason}")
        else:
            self.detail.setText("Wybierz wpis, aby zobaczyć szczegóły." if self.visible_records
                                else "Brak wyników dla bieżącego filtru.")

    def export(self):
        name, _ = QFileDialog.getSaveFileName(self, "Eksport historii", "historia.csv", "CSV (*.csv)")
        if not name:
            return
        try:
            with Path(name).open("w", newline="", encoding="utf-8-sig") as stream:
                writer = csv.writer(stream, delimiter=";")
                writer.writerow(("Czas lokalny", "Akcja", "Stan"))
                for stamp, outcome in self.visible_records:
                    writer.writerow((datetime.fromtimestamp(stamp).isoformat(timespec="seconds"),
                                     outcome.action_id, self.category(outcome)[1]))
        except OSError as exc:
            QMessageBox.warning(self, "Eksport nieudany", str(exc))

    def clear(self):
        if QMessageBox.question(self, "Usunąć wpisy?", "Usunąć całą historię bieżącej sesji?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.window._runtime.clear_history()
            self.refresh_history()

