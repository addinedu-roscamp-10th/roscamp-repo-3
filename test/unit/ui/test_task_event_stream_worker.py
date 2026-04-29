import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication


_APP = None


def _app():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def test_task_event_stream_worker_emits_pushed_batches(monkeypatch):
    _app()

    from ui.utils.pages.caregiver import task_event_stream_worker
    from ui.utils.pages.caregiver.task_event_stream_worker import TaskEventStreamWorker

    class FakeClient:
        def listen(self, *, consumer_id, last_seq, on_batch):
            on_batch(
                {
                    "batch_end_seq": 1,
                    "events": [
                        {
                            "event_seq": 1,
                            "event_type": "TASK_UPDATED",
                            "payload": {"task_id": 1001},
                        }
                    ],
                }
            )

    monkeypatch.setattr(
        task_event_stream_worker,
        "TaskEventStreamClient",
        FakeClient,
    )

    batches = []
    worker = TaskEventStreamWorker(consumer_id="ui-admin", last_seq=0)
    worker.batch_received.connect(batches.append)
    worker.run()

    assert batches == [
        {
            "batch_end_seq": 1,
            "events": [
                {
                    "event_seq": 1,
                    "event_type": "TASK_UPDATED",
                    "payload": {"task_id": 1001},
                }
            ],
        }
    ]
    assert worker.last_seq == 1
