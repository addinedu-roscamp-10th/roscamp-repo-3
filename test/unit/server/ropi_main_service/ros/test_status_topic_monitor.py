import tomllib
from pathlib import Path

from server.ropi_main_service.ros import status_topic_monitor


def test_status_topic_monitor_parser_supports_pinky_typed_topic():
    args = status_topic_monitor.build_parser().parse_args(
        ["pinky", "--pinky-id", "pinky1", "--stale-timeout-sec", "5"]
    )

    assert args.target == "pinky"
    assert args.pinky_id == "pinky1"
    assert args.stale_timeout_sec == 5
    assert args.factory.__name__ == "_create_pinky_status_monitor"


def test_status_topic_monitor_parser_supports_arm_json_topic():
    args = status_topic_monitor.build_parser().parse_args(
        ["arm-json", "--arm-id", "arm2"]
    )

    assert args.target == "arm-json"
    assert args.arm_id == "arm2"
    assert args.stale_timeout_sec == status_topic_monitor.DEFAULT_STALE_TIMEOUT_SEC
    assert args.factory.__name__ == "_create_arm_json_status_monitor"


def test_status_topic_monitor_is_registered_as_project_script():
    pyproject = tomllib.loads((Path(__file__).parents[5] / "pyproject.toml").read_text())

    assert (
        pyproject["project"]["scripts"]["ropi-status-topic-monitor"]
        == "server.ropi_main_service.ros.status_topic_monitor:main"
    )
