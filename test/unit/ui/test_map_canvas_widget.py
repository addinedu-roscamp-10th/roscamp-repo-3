import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication


_APP = None


def _app():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def test_map_canvas_loads_server_assets_and_converts_coordinates():
    _app()

    from ui.utils.widgets.map_canvas import MapCanvasWidget

    canvas = MapCanvasWidget()

    try:
        canvas.load_map_from_assets(
            yaml_text=("image: map.pgm\nresolution: 0.02\norigin: [-0.2, -0.7, 0.0]\n"),
            pgm_bytes=b"P5\n2 2\n255\n\x00\x80\xc0\xff",
            cache_key=("map_test", "yaml-sha", "pgm-sha"),
        )

        assert canvas.map_loaded is True
        assert canvas.map_image_size == (2, 2)
        assert canvas.world_to_pixel({"x": -0.18, "y": -0.68}) == (1, 1)

        world_pose = canvas.pixel_to_world((1, 1))
        assert world_pose == {"x": -0.18, "y": -0.68}
        assert canvas.contains_world_pose({"x": -0.18, "y": -0.68}) is True
        assert canvas.contains_world_pose({"x": -0.201, "y": -0.68}) is False
        assert canvas.contains_world_pose({"x": -0.24, "y": -0.68}) is False
    finally:
        canvas.close()


def test_map_canvas_uses_compact_image_gutter():
    _app()

    from ui.utils.widgets.map_canvas import MapCanvasWidget

    canvas = MapCanvasWidget()

    try:
        canvas.resize(200, 200)
        canvas.load_map_from_assets(
            yaml_text="image: map.pgm\nresolution: 1.0\norigin: [0.0, 0.0, 0.0]\n",
            pgm_bytes=b"P5\n2 2\n255\n\x00\x80\xc0\xff",
            cache_key=("compact-gutter", "yaml-sha", "pgm-sha"),
        )

        target = canvas.image_target_rect()

        assert target.left() <= 4.0
        assert target.top() <= 4.0
    finally:
        canvas.close()


def test_patrol_overlay_keeps_existing_path_based_loading_contract():
    _app()

    from ui.utils.widgets.map_canvas import MapCanvasWidget
    from ui.utils.widgets.map_overlay import PatrolMapOverlay

    overlay = PatrolMapOverlay()

    try:
        assert isinstance(overlay, MapCanvasWidget)

        overlay.render(
            {
                "task_type": "PATROL",
                "patrol_map": {
                    "yaml_path": "device/ropi_mobile/src/ropi_nav_config/maps/map_test11_0423.yaml",
                    "pgm_path": "device/ropi_mobile/src/ropi_nav_config/maps/map_test11_0423.pgm",
                },
                "patrol_path": {
                    "poses": [
                        {"x": 0.1665755137108074, "y": -0.4496830900440016},
                        {"x": 1.6946025435218914, "y": 0.0043433854992070454},
                    ],
                },
            }
        )

        assert overlay.map_loaded is True
        assert overlay.map_image_size == (105, 59)
        assert overlay.route_pixel_points == [(18, 46), (94, 24)]
    finally:
        overlay.close()
