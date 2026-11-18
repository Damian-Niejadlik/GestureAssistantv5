from src.gesture_assistant.ui.main_window import MainWindow


def test_workspace_navigation_and_empty_history(qapp, tmp_path):
    window = MainWindow(tmp_path / "config.json")
    try:
        workspace = window._workspace
        for index, button in enumerate(workspace.nav):
            button.click()
            assert workspace.pages.currentIndex() == index
            assert button.isChecked()
        workspace.navigate(2)
        assert workspace.rows.count() == 0
        assert not workspace.export_button.isEnabled()
    finally:
        window.close()


def test_error_preserves_camera_failure_message(qapp, tmp_path):
    window = MainWindow(tmp_path / "config.json")
    try:
        window._on_error("Nie można otworzyć kamery.")
        assert window._runtime.safety.paused
        assert "Błąd kamery" in window._status_label.text()
        assert "Nie można otworzyć" in window._error_label.text()
    finally:
        window.close()

