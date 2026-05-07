import builtins
import importlib
from unittest.mock import patch

from server.ropi_main_service.ros import main as ros_main


class FakeLogger:
    def __init__(self):
        self.warnings = []

    def warning(self, message):
        self.warnings.append(message)


class FakeNode:
    def __init__(self):
        self.logger = FakeLogger()

    def get_logger(self):
        return self.logger


def test_ros_main_module_import_does_not_require_guide_tracking_message():
    module = importlib.import_module("server.ropi_main_service.ros.main")

    assert module.main is ros_main.main
    assert not hasattr(module, "_build_guide_tracking_update_publisher")


def test_guide_runtime_subscriber_is_optional_when_interface_is_missing():
    node = FakeNode()
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "server.ropi_main_service.ros.guide_runtime_subscriber":
            raise ImportError("cannot import name 'GuidePhaseSnapshot'")
        return original_import(name, globals, locals, fromlist, level)

    with patch("builtins.__import__", side_effect=fake_import):
        subscriber = ros_main._build_guide_runtime_subscriber(node)

    assert subscriber is None
    assert node.logger.warnings
    assert "Guide runtime subscriber disabled" in node.logger.warnings[0]
