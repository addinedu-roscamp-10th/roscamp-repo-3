import math
import tomllib
from pathlib import Path

from server.ropi_main_service.ros import status_runtime_subscriber


def test_status_runtime_subscriber_converts_numeric_task_ids_only():
    assert status_runtime_subscriber._numeric_task_id("123") == 123
    assert status_runtime_subscriber._numeric_task_id("manual_task") is None
    assert status_runtime_subscriber._numeric_task_id("") is None


def test_status_runtime_subscriber_computes_yaw_from_quaternion():
    yaw = status_runtime_subscriber._yaw_from_quaternion(
        x=0.0,
        y=0.0,
        z=math.sin(math.pi / 4.0),
        w=math.cos(math.pi / 4.0),
    )

    assert yaw == pytest_approx(math.pi / 2.0)


def test_runtime_status_view_maps_to_robot_runtime_status_payload():
    view = status_runtime_subscriber.RuntimeStatusView(
        robot_id="pinky1",
        robot_kind="PINKY",
        runtime_state="RUNNING",
        active_task_id=1,
        battery_percent=87.5,
        pose_x=1.2,
        pose_y=0.8,
        pose_yaw=0.0,
        frame_id="map",
        fault_code=None,
    )

    assert view.to_db_status() == {
        "robot_id": "pinky1",
        "robot_kind": "PINKY",
        "runtime_state": "RUNNING",
        "active_task_id": 1,
        "battery_percent": 87.5,
        "pose_x": 1.2,
        "pose_y": 0.8,
        "pose_yaw": 0.0,
        "frame_id": "map",
        "fault_code": None,
    }


def test_ros_service_main_wires_status_runtime_subscriber_and_db_writer():
    source = (
        Path(__file__).parents[5]
        / "server"
        / "ropi_main_service"
        / "ros"
        / "main.py"
    ).read_text(encoding="utf-8")

    assert "get_default_background_db_writer" in source
    assert "db_writer.start()" in source
    assert "_build_status_runtime_subscriber(" in source
    assert "await db_writer.stop()" in source


def test_status_runtime_subscriber_module_is_packaged_with_project():
    pyproject = tomllib.loads((Path(__file__).parents[5] / "pyproject.toml").read_text())

    assert "server" in pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]


def pytest_approx(value):
    import pytest

    return pytest.approx(value)
