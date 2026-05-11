import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QWidget


_APP = None


def _app():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


class FakeTimer:
    def __init__(self):
        self.single_shot = False
        self.started = []
        self.stopped = False
        self._callback = None
        self.timeout = self

    def setSingleShot(self, value):
        self.single_shot = bool(value)

    def connect(self, callback):
        self._callback = callback

    def start(self, interval_ms):
        self.started.append(interval_ms)

    def stop(self):
        self.stopped = True

    def fire(self):
        self._callback()


def test_debounced_refresh_uses_single_shot_timer_and_runs_callback():
    _app()

    from ui.utils.core.stream_refresh import DebouncedRefresh

    calls = []
    fake_timer = FakeTimer()
    refresh = DebouncedRefresh(
        owner=None,
        interval_ms=300,
        callback=lambda: calls.append("refresh"),
        timer_factory=lambda _owner: fake_timer,
    )

    refresh.schedule()
    fake_timer.fire()
    refresh.stop()

    assert fake_timer.single_shot is True
    assert fake_timer.started == [300]
    assert fake_timer.stopped is True
    assert calls == ["refresh"]


def test_visible_deferred_refresh_defers_hidden_and_retries_while_busy():
    app = _app()

    from ui.utils.core.stream_refresh import VisibleDeferredRefresh

    widget = QWidget()
    scheduled = []
    calls = []
    busy = {"value": True}
    refresh = VisibleDeferredRefresh(
        owner=widget,
        interval_ms=200,
        callback=lambda: calls.append("refresh"),
        is_busy=lambda: busy["value"],
        single_shot=lambda delay, callback: scheduled.append((delay, callback)),
    )

    refresh.schedule()

    assert refresh.deferred is True
    assert refresh.pending is False
    assert scheduled == []

    widget.show()
    app.processEvents()
    refresh.handle_show()

    assert refresh.deferred is False
    assert refresh.pending is True
    assert len(scheduled) == 1

    scheduled.pop(0)[1]()

    assert calls == []
    assert refresh.pending is True
    assert len(scheduled) == 1

    busy["value"] = False
    scheduled.pop(0)[1]()

    assert calls == ["refresh"]
    assert refresh.pending is False

    widget.close()


def test_stream_reconnect_state_consumes_restart_request_once():
    from ui.utils.core.stream_refresh import StreamReconnectState

    state = StreamReconnectState(delay_ms=1500)

    state.request_restart()

    assert state.consume_restart_request() == 1500
    assert state.consume_restart_request() is None

    state.request_restart()
    state.cancel()

    assert state.consume_restart_request() is None
