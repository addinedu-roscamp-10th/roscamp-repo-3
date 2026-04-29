from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal

from server.ropi_main_service.transport.tcp_protocol import MESSAGE_CODE_HEARTBEAT
from ui.utils.config.network_config import CONTROL_SERVER_TIMEOUT, HEARTBEAT_INTERVAL_MS
from ui.utils.network.tcp_client import TcpClientError, send_request


class HeartbeatWorker(QObject):
    finished = pyqtSignal(bool, str)

    def run(self):
        try:
            response = send_request(MESSAGE_CODE_HEARTBEAT, {})
            if not response.get("ok"):
                message = str(response.get("error", "서버 heartbeat 실패"))
                self.finished.emit(False, message)
                return

            payload = response.get("payload", {})
            self.finished.emit(True, str(payload.get("message", "메인 서버 연결 정상")))
        except TcpClientError as exc:
            self.finished.emit(False, str(exc))
        except Exception as exc:
            self.finished.emit(False, str(exc))


class HeartbeatMonitor(QObject):
    status_changed = pyqtSignal(bool, str)

    def __init__(self, interval_ms: int = HEARTBEAT_INTERVAL_MS, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._beat)
        self._thread = None
        self._worker = None
        self._stop_wait_ms = max(1000, int((CONTROL_SERVER_TIMEOUT * 2 + 0.5) * 1000))

    def start(self):
        self._beat()
        self._timer.start()

    def stop(self):
        self._timer.stop()
        thread = self._thread
        if thread is None:
            return

        if thread.isRunning():
            thread.quit()
            if not thread.wait(self._stop_wait_ms):
                return

        self._clear_worker()

    def _beat(self):
        if self._thread is not None and self._thread.isRunning():
            return

        thread = QThread(self)
        worker = HeartbeatWorker()
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.finished.connect(self._handle_worker_result)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_worker)

        self._thread = thread
        self._worker = worker
        thread.start()

    def _handle_worker_result(self, ok: bool, message: str):
        self.status_changed.emit(ok, message)

    def _clear_worker(self):
        self._worker = None
        self._thread = None
