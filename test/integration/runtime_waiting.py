import time


def wait_for_qt(app, predicate, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.05)

    app.processEvents()
    return predicate()


def wait_for_condition(predicate, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)

    return predicate()
