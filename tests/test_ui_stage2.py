from PySide6.QtCore import QSize

from src.gesture_assistant.ui.camera_view import CameraView
from src.gesture_assistant.ui.main_window import MainWindow


def test_camera_view_preserves_aspect(qapp):
    view = CameraView()
    view.resize(1000, 500)
    rect = view._scaled_target_rect(QSize(640, 480))
    assert abs(rect.width() / rect.height() - 640 / 480) < 0.01
    assert rect.width() <= view.width()
    assert rect.height() <= view.height()
    view.close()


def test_diagnostic_panel_constructs_without_camera(qapp, tmp_path):
    window = MainWindow(config_path=tmp_path / "gui.json")
    assert window._worker is None
    assert "Gest" in window._diagnostic_label.text()
    assert window._start_button.isEnabled()
    window.close()


def test_actions_start_paused_and_no_executor_is_running(qapp, tmp_path):
    window = MainWindow(config_path=tmp_path / "gui.json")

    try:
        assert window._worker is None
        assert window._runtime.safety.paused
        assert window._runtime.executor.dry_run
        assert not window._runtime.executor.handlers
        assert not window._runtime.is_running

        window._toggle_actions_pause()

        assert window._runtime.safety.paused
        assert not window._runtime.is_running
        assert "Najpierw uruchom kamerę" in window._error_label.text()

        window._stop_analysis()

        assert window._runtime.safety.paused

    finally:
        window.close()


def test_saving_global_url_keeps_other_gestures_inheriting(qapp, tmp_path):
    window = MainWindow(config_path=tmp_path / "gui.json")
    try:
        palm = window._signal_row_widgets["OPEN_PALM"]
        assert palm["combo"].currentData() == "inherit"
        palm["combo"].setCurrentIndex(palm["combo"].findData("browser.open_url"))
        palm["allowed_check"].setChecked(True)
        palm["url_edit"].setText("https://example.com")
        window._save_bindings_from_ui()
        assert window._config["bindings"] == {"OPEN_PALM": "browser.open_url"}
        assert "browser.open_url" in window._config["allowed_actions"]
        assert window._runtime.safety.paused
        palm = window._signal_row_widgets["OPEN_PALM"]
        palm["combo"].setCurrentIndex(palm["combo"].findData("inherit"))
        window._save_bindings_from_ui()
        assert "OPEN_PALM" not in window._config["bindings"]
    finally:
        window.close()


def test_live_button_keeps_checkbox_and_runtime_in_sync(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    window = MainWindow(config_path=tmp_path / "gui.json")
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: QMessageBox.StandardButton.Yes)
    try:
        window._toggle_execution_mode()
        assert not window._config["execution"]["dry_run"]
        assert not window._dry_run_check.isChecked()
        assert not window._runtime.executor.dry_run
        assert not window._runtime.safety.config["execution"]["dry_run"]
        assert window._runtime.safety.paused
        window._save_settings_from_ui()
        assert not window._runtime.executor.dry_run
        window._toggle_execution_mode()
        assert window._dry_run_check.isChecked()
        assert window._runtime.executor.dry_run and window._runtime.safety.paused
    finally:
        window.close()

