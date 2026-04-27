from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from server.ropi_main_service.transport.tcp_protocol import MESSAGE_CODE_HEARTBEAT
from ui.utils.config.network_config import HEARTBEAT_INTERVAL_MS
from ui.utils.network.tcp_client import TcpClientError, send_request


class HeartbeatMonitor(QObject):
    status_changed = pyqtSignal(bool, str)

    def __init__(self, interval_ms: int = HEARTBEAT_INTERVAL_MS, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._beat)

    def start(self):
        self._beat()
        self._timer.start()

    def stop(self):
        self._timer.stop()

    def _beat(self):
        try:
            response = send_request(MESSAGE_CODE_HEARTBEAT, {})
            if not response.get("ok"):
                message = str(response.get("error", "서버 heartbeat 실패"))
                self.status_changed.emit(False, message)
                return

            payload = response.get("payload", {})
            self.status_changed.emit(True, str(payload.get("message", "메인 서버 연결 정상")))
        except TcpClientError as exc:
            self.status_changed.emit(False, str(exc))
