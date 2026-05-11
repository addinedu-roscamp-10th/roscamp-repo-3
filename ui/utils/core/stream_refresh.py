from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QTimer


class DebouncedRefresh:
    def __init__(
        self,
        *,
        owner,
        interval_ms: int,
        callback: Callable[[], None],
        timer_factory: Callable[[object], object] | None = None,
    ):
        self.interval_ms = int(interval_ms)
        self._callback = callback
        timer_factory = timer_factory or QTimer
        self.timer = timer_factory(owner)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._callback)

    def schedule(self):
        self.timer.start(self.interval_ms)

    def stop(self):
        self.timer.stop()


class VisibleDeferredRefresh:
    def __init__(
        self,
        *,
        owner,
        interval_ms: int,
        callback: Callable[[], None],
        is_busy: Callable[[], bool] | None = None,
        single_shot: Callable[[int, Callable[[], None]], None] | None = None,
    ):
        self.owner = owner
        self.interval_ms = int(interval_ms)
        self._callback = callback
        self._is_busy = is_busy or (lambda: False)
        self._single_shot = single_shot or QTimer.singleShot
        self.pending = False
        self.deferred = False

    def schedule(self):
        if not self.owner.isVisible():
            self.deferred = True
            return
        if self.pending:
            return
        self.pending = True
        self._single_shot(self.interval_ms, self.run)

    def run(self):
        if not self.owner.isVisible():
            self.pending = False
            self.deferred = True
            return
        if self._is_busy():
            self._single_shot(self.interval_ms, self.run)
            return
        self.pending = False
        self._callback()

    def handle_show(self):
        if not self.deferred:
            return
        self.deferred = False
        self.schedule()

    def reset(self):
        self.pending = False
        self.deferred = False


class StreamReconnectState:
    def __init__(self, *, delay_ms: int = 1000):
        self.delay_ms = int(delay_ms)
        self.enabled = True
        self.restart_requested = False

    def reset_request(self):
        self.restart_requested = False

    def request_restart(self):
        if self.enabled:
            self.restart_requested = True

    def consume_restart_request(self) -> int | None:
        if not self.enabled or not self.restart_requested:
            return None
        self.restart_requested = False
        return self.delay_ms

    def cancel(self):
        self.enabled = False
        self.restart_requested = False

    def enable(self):
        self.enabled = True
        self.restart_requested = False


__all__ = [
    "DebouncedRefresh",
    "StreamReconnectState",
    "VisibleDeferredRefresh",
]
