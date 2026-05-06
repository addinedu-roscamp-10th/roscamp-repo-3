import os
import math
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication


_APP = None
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _app():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def test_patrol_map_overlay_loads_pgm_yaml_and_converts_world_coordinates():
    _app()

    from ui.utils.widgets.map_overlay import PatrolMapOverlay

    overlay = PatrolMapOverlay()

    try:
        overlay.render(
            {
                "task_type": "PATROL",
                "patrol_map": {
                    "map_id": "map_test11_0423",
                    "frame_id": "map",
                    "yaml_path": str(
                        PROJECT_ROOT
                        / "device/ropi_mobile/src/ropi_nav_config/maps/map_test11_0423.yaml"
                    ),
                    "pgm_path": str(
                        PROJECT_ROOT
                        / "device/ropi_mobile/src/ropi_nav_config/maps/map_test11_0423.pgm"
                    ),
                },
                "patrol_path": {
                    "frame_id": "map",
                    "waypoint_count": 3,
                    "current_waypoint_index": 1,
                    "poses": [
                        {
                            "x": 0.1665755137108074,
                            "y": -0.4496830900440016,
                            "yaw": 1.57,
                        },
                        {
                            "x": 1.6946025435218914,
                            "y": 0.0043433854992070454,
                            "yaw": 0.0,
                        },
                    ],
                },
                "pose": {"x": 1.2, "y": 0.4, "yaw": 0.0},
                "fall_alert": {
                    "alert_pose": {"x": 0.9308, "y": 0.185, "yaw": 0.0},
                },
            }
        )

        assert overlay.map_loaded is True
        assert overlay.map_image_size == (105, 59)
        assert overlay.route_pixel_points[0] == (18, 46)
        assert overlay.route_pixel_points[1] == (94, 24)
        assert overlay.route_heading_yaws == [1.57, 0.0]
        assert overlay.current_waypoint_index == 1
        assert overlay.robot_pixel_point is not None
        assert overlay.fall_alert_pixel_point == (56, 15)

        overlay.render({"task_type": "DELIVERY"})

        assert overlay.map_loaded is False
        assert overlay.status_text == "순찰 맵 미수신"
        assert overlay.fall_alert_pixel_point is None
        assert overlay.route_heading_yaws == []
    finally:
        overlay.close()


def test_map_overlay_tracks_fms_waypoint_labels_and_yaws():
    _app()

    from ui.utils.widgets.map_overlay import OperationalMapOverlay

    overlay = OperationalMapOverlay()

    try:
        overlay.show_fms_waypoint_editor(
            fms_waypoint_pixel_points=[(10, 20), (30, 40)],
            fms_waypoint_labels=["복도1", "301호앞"],
            fms_waypoint_yaws=[1.57, 0.0],
            selected_pixel_point=(10, 20),
            selected_yaw=1.57,
        )

        assert overlay.fms_waypoint_pixel_points == [(10, 20), (30, 40)]
        assert overlay.fms_waypoint_labels == ["복도1", "301호앞"]
        assert overlay.fms_waypoint_heading_yaws == [1.57, 0.0]
        assert overlay.selected_fms_waypoint_pixel_point == (10, 20)
        assert overlay.selected_fms_waypoint_heading_yaw == 1.57

        overlay.clear_configuration_overlay()

        assert overlay.fms_waypoint_pixel_points == []
        assert overlay.fms_waypoint_labels == []
        assert overlay.fms_waypoint_heading_yaws == []
        assert overlay.selected_fms_waypoint_pixel_point is None
    finally:
        overlay.close()


def test_map_overlay_builds_heading_drag_payload_from_selected_goal_pose():
    _app()

    from ui.utils.widgets.map_overlay import OperationalMapOverlay

    overlay = OperationalMapOverlay()

    try:
        overlay.load_map_from_assets(
            yaml_text="image: map.pgm\nresolution: 1.0\norigin: [0.0, 0.0, 0.0]\n",
            pgm_bytes=b"P5\n10 10\n255\n" + bytes([0] * 100),
            cache_key=("heading-test", "yaml", "pgm"),
        )
        overlay.show_goal_pose_editor(
            goal_pose_pixel_points=[(2, 7)],
            goal_pose_yaws=[0.0],
            selected_pixel_point=(2, 7),
            selected_yaw=0.0,
        )

        payload = overlay.heading_drag_payload_for_world_target({"x": 2.0, "y": 4.0})

        assert payload == {"yaw": math.pi / 2}
    finally:
        overlay.close()


def test_map_overlay_heading_handle_mouse_drag_emits_yaw_payload():
    _app()

    from ui.utils.widgets.map_overlay import OperationalMapOverlay

    overlay = OperationalMapOverlay()

    try:
        overlay.resize(200, 200)
        overlay.load_map_from_assets(
            yaml_text="image: map.pgm\nresolution: 1.0\norigin: [0.0, 0.0, 0.0]\n",
            pgm_bytes=b"P5\n10 10\n255\n" + bytes([0] * 100),
            cache_key=("heading-mouse-test", "yaml", "pgm"),
        )
        overlay.show_goal_pose_editor(
            goal_pose_pixel_points=[(2, 7)],
            goal_pose_yaws=[0.0],
            selected_pixel_point=(2, 7),
            selected_yaw=0.0,
        )
        emitted = []
        overlay.map_heading_dragged.connect(emitted.append)

        handle = overlay._selected_heading_handle_view_point()
        target = overlay.image_target_rect()
        move_point = overlay.to_view_point(
            overlay.world_to_pixel({"x": 2.0, "y": 4.0}), target
        )

        overlay.mousePressEvent(
            QMouseEvent(
                QEvent.Type.MouseButtonPress,
                handle,
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
        )
        overlay.mouseMoveEvent(
            QMouseEvent(
                QEvent.Type.MouseMove,
                move_point,
                Qt.MouseButton.NoButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
        )

        assert emitted == [{"yaw": math.pi / 2}]
    finally:
        overlay.close()


def test_map_overlay_tracks_fms_edge_pairs_and_clears_them():
    _app()

    from ui.utils.widgets.map_overlay import OperationalMapOverlay

    overlay = OperationalMapOverlay()

    try:
        overlay.show_fms_edge_editor(
            fms_waypoint_pixel_points=[(10, 20), (30, 40)],
            fms_waypoint_labels=["복도1", "복도2"],
            fms_edge_pixel_pairs=[((10, 20), (30, 40))],
            selected_edge_pixel_pair=((10, 20), (30, 40)),
        )

        assert overlay.fms_waypoint_pixel_points == [(10, 20), (30, 40)]
        assert overlay.fms_waypoint_labels == ["복도1", "복도2"]
        assert overlay.fms_edge_pixel_pairs == [((10, 20), (30, 40))]
        assert overlay.selected_fms_edge_pixel_pair == ((10, 20), (30, 40))

        overlay.clear_configuration_overlay()

        assert overlay.fms_edge_pixel_pairs == []
        assert overlay.selected_fms_edge_pixel_pair is None
    finally:
        overlay.close()


def test_map_overlay_tracks_fms_route_points_and_clears_them():
    _app()

    from ui.utils.widgets.map_overlay import OperationalMapOverlay

    overlay = OperationalMapOverlay()

    try:
        overlay.show_fms_route_editor(
            route_pixel_points=[(10, 20), (30, 40), (50, 60)],
            route_labels=["복도1", "복도2", "로비"],
            selected_route_index=1,
        )

        assert overlay.fms_route_pixel_points == [(10, 20), (30, 40), (50, 60)]
        assert overlay.fms_route_labels == ["복도1", "복도2", "로비"]
        assert overlay.selected_fms_route_index == 1

        overlay.clear_configuration_overlay()

        assert overlay.fms_route_pixel_points == []
        assert overlay.fms_route_labels == []
        assert overlay.selected_fms_route_index is None
    finally:
        overlay.close()
