from PyQt6.QtCore import QThread


def start_worker_thread(
    parent,
    *,
    worker,
    finished_handler=None,
    clear_handler=None,
    worker_signal_connections=None,
    thread_factory=QThread,
):
    thread = thread_factory(parent)
    worker.moveToThread(thread)

    thread.started.connect(worker.run)
    if finished_handler is not None:
        worker.finished.connect(finished_handler)
    for signal_name, handler in (worker_signal_connections or {}).items():
        getattr(worker, signal_name).connect(handler)

    worker.finished.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    if clear_handler is not None:
        thread.finished.connect(clear_handler)

    thread.start()
    return thread, worker


__all__ = ["start_worker_thread"]
