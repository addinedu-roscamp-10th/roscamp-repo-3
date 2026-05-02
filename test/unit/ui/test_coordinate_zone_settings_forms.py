import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDoubleSpinBox, QLabel


_APP = None


def _app():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def test_coordinate_zone_settings_form_builders_export_widget_factories():
    _app()

    from ui.utils.pages.caregiver.coordinate_zone_settings_forms import (
        build_goal_pose_form,
        build_operation_zone_form,
        build_patrol_area_form,
        coordinate_spin,
        readonly_value_label,
    )

    assert callable(build_operation_zone_form)
    assert callable(build_goal_pose_form)
    assert callable(build_patrol_area_form)

    label = readonly_value_label("sampleReadonlyLabel")
    spin = coordinate_spin("sampleCoordinateSpin")

    try:
        assert isinstance(label, QLabel)
        assert label.objectName() == "sampleReadonlyLabel"
        assert label.text() == "-"
        assert isinstance(spin, QDoubleSpinBox)
        assert spin.objectName() == "sampleCoordinateSpin"
        assert spin.decimals() == 4
        assert spin.singleStep() == 0.01
    finally:
        label.deleteLater()
        spin.deleteLater()
