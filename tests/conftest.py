import pytest


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture
def wait_for_signal(qapp):
    from PySide6.QtCore import QEventLoop, QTimer

    def wait(signal, timeout_ms=5000, start=None):
        loop = QEventLoop()
        timer = QTimer()
        timer.setSingleShot(True)
        received = []

        def on_signal(*args):
            received.append(args)
            loop.quit()

        signal.connect(on_signal)
        timer.timeout.connect(loop.quit)
        timer.start(timeout_ms)
        try:
            if start is not None:
                start()
            if not received:
                loop.exec()
            assert received, "Nie otrzymano sygnału przed limitem czasu."
        finally:
            timer.stop()
            signal.disconnect(on_signal)

    return wait

