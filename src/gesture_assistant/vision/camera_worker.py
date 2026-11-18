import logging
import queue
import threading

import cv2
from PySide6.QtCore import QThread, Signal

from src.gesture_assistant.core.analysis_pipeline import AnalysisPipeline
from src.gesture_assistant.utils.time_utils import monotonic_ms
from src.gesture_assistant.vision.hand_provider import HandProvider

logger = logging.getLogger(__name__)


class CameraWorker(QThread):
    """Odczyt źródła i analiza z buforem najnowszej klatki."""

    frame_ready = Signal(object, object)
    result_ready = Signal(object)
    analysis_ready = Signal(object)
    event_ready = Signal(object)
    error = Signal(str)
    stopped = Signal()

    def __init__(
        self,
        source: int,
        provider: HandProvider,
        capture_factory=cv2.VideoCapture,
        parent=None,
        runtime=None,
        camera_settings=None,
        orientation=(False, False),
        samples=None,
    ) -> None:
        super().__init__(parent)

        if type(source) is not int or source < 0:
            raise ValueError("Źródłem musi być nieujemny numer kamery, nie plik wideo.")
        self._source = source
        self._provider = provider
        self._capture_factory = capture_factory

        self._stop_event = threading.Event()
        self._capture_finished = threading.Event()
        self._latest_frame = queue.Queue(maxsize=1)
        self._preview_lock = threading.Lock()
        self._preview = None
        self._analysis = None
        self._pipeline = AnalysisPipeline()
        self._runtime = runtime
        self._orientation = orientation
        self._pipeline.samples = samples or {}
        if runtime is not None:
            self._pipeline.active_signals = getattr(runtime, "active_gesture_signals", lambda: set())
        self._camera_settings = camera_settings
        self._applied_orientation = orientation
        self._orientation_revision = 0

    def set_orientation(self, mirror: bool, rotate: bool) -> None:
        if self._runtime is not None:
            self._runtime.pause()
            self._runtime.cancel_pending()

        orientation = (mirror, rotate)
        with self._preview_lock:
            self._orientation = orientation
            self._orientation_revision += 1
            self._preview = None
            self._analysis = None

    def run(self) -> None:
        capture_thread = threading.Thread(
            target=self._capture_loop,
            name="GestureAssistantCapture",
            daemon=False,
        )

        try:
            capture_thread.start()

            last_analysis_start = None
            while not self._stop_event.is_set():
                if self._camera_settings is not None and last_analysis_start is not None:
                    period = 1000 / self._camera_settings["fps_limit"]
                    delay = max(0, period - (monotonic_ms() - last_analysis_start)) / 1000
                    if self._stop_event.wait(delay):
                        break
                try:
                    frame, timestamp_ms = self._latest_frame.get(timeout=0.1)
                except queue.Empty:
                    if self._capture_finished.is_set():



                        try:
                            frame, timestamp_ms = self._latest_frame.get_nowait()
                        except queue.Empty:
                            break
                    else:
                        continue

                last_analysis_start = monotonic_ms()
                try:
                    with self._preview_lock:
                        orientation = self._orientation
                        orientation_revision = self._orientation_revision

                    if orientation != self._applied_orientation:
                        self._pipeline.smoother.reset()
                        self._pipeline.motions.classifier.reset()
                        self._pipeline.gestures.debouncer.tracking_discontinuity()
                        self._pipeline.samples = {}
                        self._applied_orientation = orientation

                    mirror, rotate = orientation
                    if rotate:
                        frame = cv2.flip(frame, -1)
                    if mirror:
                        frame = cv2.flip(frame, 1)
                    result = self._provider.process(frame, timestamp_ms)
                    analysis = self._pipeline.process(result, frame.shape[1], frame.shape[0])

                except Exception as exc:
                    logger.exception("Błąd podczas analizy klatki.")
                    self.error.emit(f"Błąd analizy klatki: {exc}")
                    break

                with self._preview_lock:
                    if (orientation_revision != self._orientation_revision
                            or self._stop_event.is_set()):
                        continue
                    if self._runtime is not None:
                        self._runtime.observe(analysis)
                    self._preview = (frame, result)
                    self._analysis = analysis
                self.frame_ready.emit(frame, timestamp_ms)
                self.result_ready.emit(result)
                self.analysis_ready.emit(analysis)
                if analysis.gesture_event is not None or analysis.motion_event is not None:
                    self.event_ready.emit(analysis)

        except Exception as exc:
            logger.exception("Błąd uruchomienia lub pracy workera.")
            self.error.emit(f"Błąd workera: {exc}")

        finally:
            self._stop_event.set()
            if self._runtime is not None:
                self._runtime.pause()

            if capture_thread.ident is not None:


                capture_thread.join()

            try:
                close = getattr(self._provider, "close", None)
                if callable(close):
                    close()
            except Exception as exc:
                logger.exception("Błąd zamykania modelu.")
                self.error.emit(f"Błąd zamykania modelu: {exc}")
            finally:
                self.stopped.emit()

    def apply_config(self, config: dict) -> None:
        """Bezpieczne zastosowanie nowej konfiguracji do pipeline analizy."""
        if "camera" in config:
            self._camera_settings = config["camera"]
        if hasattr(self._pipeline, "apply_config"):
            self._pipeline.apply_config(config)

    def stop(self) -> None:
        """Zleca zatrzymanie bez blokowania głównego wątku GUI."""
        self._stop_event.set()
        if self._runtime is not None:
            self._runtime.pause()

    def _capture_loop(self) -> None:
        capture = None
        last_timestamp_ms = -1

        try:
            capture = self._capture_factory(self._source)

            if not capture.isOpened():
                message = f"Nie można otworzyć kamery o numerze {self._source}."

                logger.error(message)
                self.error.emit(message)
                return

            if self._camera_settings is not None:
                for prop, key in (
                    (cv2.CAP_PROP_FRAME_WIDTH, "width"),
                    (cv2.CAP_PROP_FRAME_HEIGHT, "height"),
                    (cv2.CAP_PROP_FPS, "fps_limit"),
                ):
                    if not capture.set(prop, self._camera_settings[key]):
                        logger.warning("Kamera nie przyjęła ustawienia %s", key)
            while not self._stop_event.is_set():
                opened, frame = capture.read()

                if not opened:
                    if not self._stop_event.is_set():
                        self.error.emit("Nie można odczytać kolejnej klatki z kamery.")
                    break

                if self._stop_event.is_set():
                    break

                if frame is None:
                    self.error.emit("Kamera zwróciła pustą klatkę.")
                    break

                timestamp_ms = max(
                    monotonic_ms(),
                    last_timestamp_ms + 1,
                )
                last_timestamp_ms = timestamp_ms

                self._publish_latest_frame(frame, timestamp_ms)

        except Exception as exc:
            logger.exception("Błąd odczytu kamery.")
            self.error.emit(f"Błąd kamery: {exc}")

        finally:
            try:
                if capture is not None:
                    capture.release()
            except Exception as exc:
                logger.exception("Błąd zwalniania kamery.")
                self.error.emit(f"Błąd zwalniania kamery: {exc}")
            finally:
                self._capture_finished.set()

    def _publish_latest_frame(self, frame, timestamp_ms: int) -> None:
        """Zastępuje oczekującą klatkę nowszą, jeśli bufor jest pełny."""
        item = (frame, timestamp_ms)

        try:
            self._latest_frame.put_nowait(item)
            return
        except queue.Full:

            logger.debug("Odrzucanie starszej klatki z bufora.")

        try:
            self._latest_frame.get_nowait()
        except queue.Empty:

            logger.debug("Starsza klatka została już pobrana.")



        self._latest_frame.put_nowait(item)

    def take_latest_preview(self):
        """GUI odbiera najwyżej jeden aktualny pakiet, bez kolejki sygnałów obrazu."""
        with self._preview_lock:
            preview = self._preview
            self._preview = None
            return preview

    def take_latest_analysis(self):
        """Latest diagnostics; event consumers must use analysis_ready instead."""
        with self._preview_lock:
            analysis = self._analysis
            self._analysis = None
            return analysis

