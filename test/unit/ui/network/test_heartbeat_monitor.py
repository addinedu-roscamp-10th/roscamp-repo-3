import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication


_APP = None


def _app():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


class FakeSignal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, *args):
        for callback in list(self._callbacks):
            callback(*args)


class FakeThread:
    instances = []

    def __init__(self, parent=None):
        self.parent = parent
        self.started = FakeSignal()
        self.finished = FakeSignal()
        self.started_count = 0
        self.quit_count = 0
        self.waited = False
        self._running = False
        FakeThread.instances.append(self)

    def start(self):
        self.started_count += 1
        self._running = True

    def isRunning(self):
        return self._running

    def quit(self):
        self.quit_count += 1
        self._running = False

    def wait(self, _timeout_ms=None):
        self.waited = True
        return True

    def deleteLater(self):
        pass


class FakeWorker:
    instances = []

    def __init__(self):
        self.finished = FakeSignal()
        self.thread = None
        self.deleted = False
        FakeWorker.instances.append(self)

    def moveToThread(self, thread):
        self.thread = thread

    def run(self):
        pass

    def deleteLater(self):
        self.deleted = True


def test_heartbeat_tick_starts_worker_thread_without_direct_tcp_call(monkeypatch):
    _app()

    from ui.utils.network import heartbeat

    FakeThread.instances = []
    FakeWorker.instances = []

    def fail_if_called_directly(*_args, **_kwargs):
        raise AssertionError("heartbeat must not block the UI thread with direct TCP")

    monkeypatch.setattr(heartbeat, "send_request", fail_if_called_directly)
    monkeypatch.setattr(heartbeat, "QThread", FakeThread)
    monkeypatch.setattr(heartbeat, "HeartbeatWorker", FakeWorker)

    monitor = heartbeat.HeartbeatMonitor()
    monitor._beat()

    try:
        assert len(FakeThread.instances) == 1
        assert len(FakeWorker.instances) == 1
        assert FakeThread.instances[0].started_count == 1
        assert FakeWorker.instances[0].thread is FakeThread.instances[0]
    finally:
        monitor.stop()


def test_heartbeat_tick_skips_when_previous_request_is_running(monkeypatch):
    _app()

    from ui.utils.network import heartbeat

    FakeThread.instances = []
    FakeWorker.instances = []

    monkeypatch.setattr(heartbeat, "QThread", FakeThread)
    monkeypatch.setattr(heartbeat, "HeartbeatWorker", FakeWorker)

    monitor = heartbeat.HeartbeatMonitor()
    monitor._beat()
    monitor._beat()

    try:
        assert len(FakeThread.instances) == 1
        assert len(FakeWorker.instances) == 1
    finally:
        monitor.stop()


def test_heartbeat_stop_quits_running_worker_thread(monkeypatch):
    _app()

    from ui.utils.network import heartbeat

    FakeThread.instances = []
    FakeWorker.instances = []

    monkeypatch.setattr(heartbeat, "QThread", FakeThread)
    monkeypatch.setattr(heartbeat, "HeartbeatWorker", FakeWorker)

    monitor = heartbeat.HeartbeatMonitor()
    monitor._beat()

    thread = FakeThread.instances[0]
    monitor.stop()

    assert thread.quit_count == 1
    assert thread.waited is True
    assert monitor._thread is None
    assert monitor._worker is None


def test_heartbeat_worker_maps_success_response(monkeypatch):
    from ui.utils.network import heartbeat

    monkeypatch.setattr(
        heartbeat,
        "send_request",
        lambda *_args, **_kwargs: {
            "ok": True,
            "payload": {"message": "메인 서버 연결 정상"},
        },
    )

    worker = heartbeat.HeartbeatWorker()
    results = []
    worker.finished.connect(lambda ok, message: results.append((ok, message)))

    worker.run()

    assert results == [(True, "메인 서버 연결 정상")]


def test_heartbeat_monitor_emits_worker_result_without_blocking(monkeypatch):
    app = _app()

    from ui.utils.network import heartbeat

    monkeypatch.setattr(
        heartbeat,
        "send_request",
        lambda *_args, **_kwargs: {
            "ok": True,
            "payload": {"message": "메인 서버 연결 정상"},
        },
    )

    monitor = heartbeat.HeartbeatMonitor(interval_ms=60_000)
    results = []
    monitor.status_changed.connect(lambda ok, message: results.append((ok, message)))

    monitor._beat()

    deadline = time.monotonic() + 1.0
    while not results and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)

    monitor.stop()

    assert results == [(True, "메인 서버 연결 정상")]
