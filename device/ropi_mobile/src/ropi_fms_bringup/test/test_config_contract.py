from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_nav2_fms_params_use_relative_scan_and_base_footprint():
    params = (PACKAGE_ROOT / "config" / "nav2_params_fms.yaml").read_text()

    assert "robot_base_frame: base_link" not in params
    assert "robot_base_frame: base_footprint" in params
    assert "topic: /scan" not in params
    assert "topic: scan" in params
    assert "enable_stamped_cmd_vel: true" in params
    assert "enable_stamped_cmd_vel: True" in params


def test_controller_fms_params_keep_tf_frames_local_inside_namespace():
    params = (PACKAGE_ROOT / "config" / "pinky_controllers_fms.yaml").read_text()

    assert "odom_frame_id: odom" in params
    assert "base_frame_id: base_footprint" in params
    assert "tf_frame_prefix_enable: false" in params
    assert 'tf_frame_prefix: ""' in params
