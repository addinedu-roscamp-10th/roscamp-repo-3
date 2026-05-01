from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
TASK_MONITOR_PAGE = (
    REPO_ROOT
    / "ui"
    / "utils"
    / "pages"
    / "caregiver"
    / "task_monitor_page.py"
)
TASK_REQUEST_PAGE = (
    REPO_ROOT
    / "ui"
    / "utils"
    / "pages"
    / "caregiver"
    / "task_request_page.py"
)


class FakeSignal:
    def __init__(self):
        self.connections = []

    def connect(self, slot):
        self.connections.append(slot)


class FakeThread:
    def __init__(self, parent=None):
        self.parent = parent
        self.started = FakeSignal()
        self.finished = FakeSignal()
        self.start_count = 0

    def start(self):
        self.start_count += 1

    def quit(self):
        pass

    def deleteLater(self):
        pass


class FakeWorker:
    def __init__(self):
        self.finished = FakeSignal()
        self.batch_received = FakeSignal()
        self.failed = FakeSignal()
        self.moved_to = None

    def moveToThread(self, thread):
        self.moved_to = thread

    def run(self):
        pass

    def deleteLater(self):
        pass


def _slot_names(signal):
    return [getattr(slot, "__name__", repr(slot)) for slot in signal.connections]


def test_start_worker_thread_wires_worker_lifecycle_and_extra_signals():
    from ui.utils.core.worker_threads import start_worker_thread

    worker = FakeWorker()
    finished_calls = []
    clear_calls = []
    batch_calls = []
    failed_calls = []

    thread, returned_worker = start_worker_thread(
        object(),
        worker=worker,
        finished_handler=lambda *args: finished_calls.append(args),
        clear_handler=lambda: clear_calls.append(True),
        worker_signal_connections={
            "batch_received": lambda batch: batch_calls.append(batch),
            "failed": lambda error: failed_calls.append(error),
        },
        thread_factory=FakeThread,
    )

    assert returned_worker is worker
    assert worker.moved_to is thread
    assert thread.start_count == 1
    assert "run" in _slot_names(thread.started)
    assert "<lambda>" in _slot_names(worker.finished)
    assert "quit" in _slot_names(worker.finished)
    assert "deleteLater" in _slot_names(worker.finished)
    assert "deleteLater" in _slot_names(thread.finished)
    assert "<lambda>" in _slot_names(thread.finished)
    assert "<lambda>" in _slot_names(worker.batch_received)
    assert "<lambda>" in _slot_names(worker.failed)


def test_task_request_and_monitor_pages_use_shared_worker_thread_helper():
    monitor_source = TASK_MONITOR_PAGE.read_text(encoding="utf-8")
    request_source = TASK_REQUEST_PAGE.read_text(encoding="utf-8")

    assert "from ui.utils.core.worker_threads import start_worker_thread" in monitor_source
    assert "from ui.utils.core.worker_threads import start_worker_thread" in request_source
    assert "QThread(" not in monitor_source
    assert "QThread(" not in request_source
