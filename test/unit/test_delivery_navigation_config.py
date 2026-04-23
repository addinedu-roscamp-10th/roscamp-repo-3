from server.ropi_main_service.navigation.config import get_delivery_navigation_config


def test_delivery_navigation_config_reads_return_to_dock_goal_pose_from_env(monkeypatch):
    monkeypatch.setenv(
        "ROPI_RETURN_TO_DOCK_GOAL_POSE_JSON",
        '{"header":{"frame_id":"map","stamp":{"sec":0,"nanosec":0}},"pose":{"position":{"x":0.5,"y":0.5,"z":0.0},"orientation":{"x":0.0,"y":0.0,"z":0.0,"w":1.0}}}',
    )

    config = get_delivery_navigation_config()

    assert config["return_to_dock_goal_pose"] == {
        "header": {
            "frame_id": "map",
            "stamp": {"sec": 0, "nanosec": 0},
        },
        "pose": {
            "position": {"x": 0.5, "y": 0.5, "z": 0.0},
            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
        },
    }
