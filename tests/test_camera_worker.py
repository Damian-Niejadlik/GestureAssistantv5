import threading

import numpy as np
import pytest

from src.gesture_assistant.vision.camera_worker import CameraWorker
from src.gesture_assistant.vision.hand_provider import HandResult


class FakeHandProvider:
    def __init__(self):
        self.seen = []
        self.processed = threading.Semaphore(0)
        self.closed = False

    def process(self, frame_bgr, timestamp_ms):
        self.seen.append((int(frame_bgr[0, 0, 0]), timestamp_ms))
        self.processed.release()
        return HandResult(len(self.seen), timestamp_ms, ())

    def close(self):
        self.closed = True


class FakeCapture:
    def __init__(self, frames, opened=True, provider=None):
        self.frames = list(frames)
        self.opened = opened
        self.provider = provider
        self.index = 0
        self.released = False

    def isOpened(self):
        return self.opened

    def read(self):
        if self.provider is not None and self.index:
            assert self.provider.processed.acquire(timeout=3), "Brak potwierdzenia analizy."
        if self.index == len(self.frames):
            return False, None
        frame = self.frames[self.index]
        self.index += 1
        return True, frame

    def release(self):
        self.released = True


def make_frame(value):
    return np.full((24, 32, 3), value, dtype=np.uint8)


def finish(worker, qapp):
    assert worker.wait(5000), "Worker nie zakończył pracy."
    qapp.processEvents()
    assert not worker.isRunning()


def test_worker_processes_frames_and_releases_capture(qapp):
    provider = FakeHandProvider()
    capture = FakeCapture([make_frame(i) for i in range(3)], provider=provider)
    worker = CameraWorker(0, provider, capture_factory=lambda _: capture)
    frames, results, errors = [], [], []
    worker.frame_ready.connect(lambda f, t: frames.append((f, t)))
    worker.result_ready.connect(results.append)
    worker.error.connect(errors.append)
    try:
        worker.start()
        finish(worker, qapp)
        assert len(frames) == 3
        assert len(results) == 3
        assert errors
        assert capture.released and provider.closed
        timestamps = [t for _, t in frames]
        assert timestamps == sorted(set(timestamps))
        assert [int(f[0, 0, 0]) for f, _ in frames] == [0, 1, 2]
    finally:
        worker.stop()
        assert worker.wait(5000)


def test_worker_reports_camera_open_error(qapp):
    provider = FakeHandProvider()
    capture = FakeCapture([], opened=False)
    worker = CameraWorker(0, provider, capture_factory=lambda _: capture)
    errors = []
    worker.error.connect(errors.append)
    worker.start()
    finish(worker, qapp)
    assert len(errors) == 1
    assert "Nie można otworzyć kamery" in errors[0]
    assert capture.released and provider.closed


@pytest.mark.parametrize("source", ["bad.mp4", "0", -1, True])
def test_worker_rejects_non_camera_sources(source):
    with pytest.raises(ValueError, match="numer kamery"):
        CameraWorker(source, FakeHandProvider())


def test_worker_drops_old_frames_when_analysis_is_slow(qapp):
    entered, release, produced = threading.Event(), threading.Event(), threading.Event()

    class BlockedProvider(FakeHandProvider):
        def process(self, frame_bgr, timestamp_ms):
            if not self.seen:
                entered.set()
                assert release.wait(3), "Nie zwolniono kontrolowanej analizy."
            return super().process(frame_bgr, timestamp_ms)

    class BurstCapture(FakeCapture):
        def read(self):
            if self.index == len(self.frames):

                produced.set()
                return False, None
            if self.index == 1:
                assert entered.wait(3), "Analiza pierwszej klatki nie wystartowała."
            return super().read()

    provider = BlockedProvider()
    capture = BurstCapture([make_frame(i) for i in range(20)])
    worker = CameraWorker(0, provider, capture_factory=lambda _: capture)
    try:
        worker.start()
        assert produced.wait(3)
        release.set()
        finish(worker, qapp)
        assert [value for value, _ in provider.seen] == [0, 19]
        assert 1 <= len(provider.seen) < 20
        assert capture.released and provider.closed
    finally:
        release.set()
        worker.stop()
        assert worker.wait(5000)


def test_worker_stop_releases_capture(qapp):
    entered, release = threading.Event(), threading.Event()

    class WaitingCapture(FakeCapture):
        def read(self):
            entered.set()
            assert release.wait(3)
            return True, make_frame(0)

    provider = FakeHandProvider()
    capture = WaitingCapture([])
    worker = CameraWorker(0, provider, capture_factory=lambda _: capture)
    try:
        worker.start()
        assert entered.wait(3)
        worker.stop()
        release.set()
        finish(worker, qapp)
        assert capture.released and provider.closed
        assert not worker.isRunning()
    finally:
        release.set()
        worker.stop()
        assert worker.wait(5000)


def test_provider_error_still_closes_resources(qapp):
    class FailingProvider(FakeHandProvider):
        def process(self, frame_bgr, timestamp_ms):
            raise RuntimeError("Kontrolowany błąd testowy")

    provider = FailingProvider()
    capture = FakeCapture([make_frame(1)])
    worker = CameraWorker(0, provider, capture_factory=lambda _: capture)
    errors = []
    worker.error.connect(errors.append)
    worker.start()
    finish(worker, qapp)
    assert any("Kontrolowany błąd testowy" in message for message in errors)
    assert capture.released and provider.closed


def test_fixed_orientation_does_not_reset_pipeline_every_frame(qapp):
    provider = FakeHandProvider()
    capture = FakeCapture([make_frame(i) for i in range(3)], provider=provider)
    worker = CameraWorker(0, provider, capture_factory=lambda _: capture)
    worker._pipeline.samples = {"FIST": [object()]}
    try:
        worker.start()
        finish(worker, qapp)
        assert len(provider.seen) == 3
        assert worker._pipeline.samples["FIST"]
    finally:
        worker.stop()
        assert worker.wait(5000)

