from PyQt6.QtCore import QObject, pyqtSignal

from ui.utils.network.task_event_stream_client import TaskEventStreamClient


class TaskEventStreamWorker(QObject):
    batch_received = pyqtSignal(object)
    failed = pyqtSignal(object)
    finished = pyqtSignal()

    def __init__(self, *, consumer_id, last_seq=0, client=None):
        super().__init__()
        self.consumer_id = str(consumer_id or "").strip()
        self.last_seq = int(last_seq or 0)
        self.client = client
        self._stop_requested = False

    def run(self):
        self.client = self.client or TaskEventStreamClient()

        if self._stop_requested:
            self._close_client()
            self.finished.emit()
            return

        try:
            self.client.listen(
                consumer_id=self.consumer_id,
                last_seq=self.last_seq,
                on_batch=self._handle_batch,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()

    def _handle_batch(self, batch):
        if isinstance(batch, dict):
            try:
                self.last_seq = int(batch.get("batch_end_seq") or self.last_seq)
            except (TypeError, ValueError):
                pass

        self.batch_received.emit(batch)

    def stop(self):
        self._stop_requested = True
        self._close_client()

    def _close_client(self):
        if self.client is not None and hasattr(self.client, "close"):
            self.client.close()


__all__ = ["TaskEventStreamWorker"]
