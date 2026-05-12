import os
import subprocess
import sys
from collections import OrderedDict

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_UI_SUBPROCESS_ENV = "ROPI_UI_PYTEST_SUBPROCESS"


def pytest_collection_modifyitems(config, items):
    if os.environ.get(_UI_SUBPROCESS_ENV) == "1":
        return

    explicit_node = any("::" in arg for arg in config.args)
    if explicit_node:
        for item in items:
            item._ui_subprocess_target = item.nodeid
        return

    grouped_items = OrderedDict()
    for item in items:
        grouped_items.setdefault(str(item.path), []).append(item)

    representative_items = []
    for path, group in grouped_items.items():
        representative = group[0]
        representative._ui_subprocess_target = path
        representative_items.append(representative)
    items[:] = representative_items


def pytest_runtest_protocol(item, nextitem):
    if os.environ.get(_UI_SUBPROCESS_ENV) == "1":
        return None

    target = getattr(item, "_ui_subprocess_target", None)
    if target is None:
        return None

    item.ihook.pytest_runtest_logstart(
        nodeid=item.nodeid,
        location=item.location,
    )
    call = pytest.CallInfo.from_call(
        lambda: _run_ui_pytest_subprocess(target),
        when="call",
    )
    report = pytest.TestReport.from_item_and_call(item, call)
    item.ihook.pytest_runtest_logreport(report=report)
    item.ihook.pytest_runtest_logfinish(
        nodeid=item.nodeid,
        location=item.location,
    )
    return True


@pytest.fixture(scope="session")
def qt_ui_app():
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
    _cleanup_qt_widgets(app)


@pytest.fixture(autouse=True)
def _isolate_qt_widgets(qt_ui_app):
    _cleanup_qt_widgets(qt_ui_app)
    yield
    _cleanup_qt_widgets(qt_ui_app)


def _run_ui_pytest_subprocess(target):
    env = os.environ.copy()
    env[_UI_SUBPROCESS_ENV] = "1"
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")

    completed = subprocess.run(
        [sys.executable, "-m", "pytest", target, "-q"],
        cwd=os.getcwd(),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(
            "UI pytest subprocess failed for "
            f"{target} with exit code {completed.returncode}\n\n"
            f"{completed.stdout}"
        )


def _cleanup_qt_widgets(app):
    if app is None:
        return

    app.processEvents()
    app.setStyleSheet("")

    from PyQt6.QtWidgets import QApplication

    for widget in list(QApplication.topLevelWidgets()):
        try:
            widget.close()
        except RuntimeError:
            continue

    app.setStyleSheet("")
    app.processEvents()
