from dataclasses import dataclass

from ui.utils.pages.caregiver.coordinate_boundary_editing import (
    boundary_json_from_vertices,
)


@dataclass
class OperationZoneEditorController:
    selected_row: dict | None = None
    selected_index: int | None = None
    mode: str | None = None
    dirty: bool = False
    syncing_form: bool = False

    def select(self, row_index, rows):
        row_index = int(row_index)
        row = rows[row_index]
        selected = dict(row if isinstance(row, dict) else {})
        self.selected_row = selected
        self.selected_index = row_index
        self.mode = "edit"
        self.dirty = False
        return selected

    def start_create(self):
        self.selected_row = None
        self.selected_index = None
        self.mode = "create"
        self.dirty = False
        return {
            "zone_id": "",
            "zone_name": "",
            "zone_type": "ROOM",
            "is_enabled": True,
        }

    def mark_dirty(self, *, selected_edit_type):
        if self.syncing_form or selected_edit_type != "operation_zone":
            return False
        self.dirty = True
        return True

    def apply_saved_row(self, row):
        self.selected_row = dict(row if isinstance(row, dict) else {})
        self.mode = "edit"
        self.dirty = False

    def clear(self):
        self.selected_row = None
        self.selected_index = None
        self.mode = None
        self.dirty = False
        self.syncing_form = False


def build_operation_zone_save_payload(
    *,
    mode,
    selected_operation_zone,
    map_profile,
    zone_id,
    zone_name,
    zone_type,
    is_enabled,
):
    if str(mode or "").strip() == "create":
        profile = map_profile if isinstance(map_profile, dict) else {}
        return {
            "zone_id": _stripped_text(zone_id),
            "zone_name": _stripped_text(zone_name),
            "zone_type": _stripped_text(zone_type),
            "map_id": profile.get("map_id"),
            "is_enabled": bool(is_enabled),
        }

    selected = (
        selected_operation_zone
        if isinstance(selected_operation_zone, dict)
        else {}
    )
    return {
        "zone_id": _stripped_text(zone_id),
        "expected_revision": _int_or_default(selected.get("revision")),
        "zone_name": _stripped_text(zone_name),
        "zone_type": _stripped_text(zone_type),
        "is_enabled": bool(is_enabled),
    }


def build_operation_zone_boundary_save_payload(
    *,
    selected_operation_zone,
    boundary_vertices,
    frame_id,
):
    selected = (
        selected_operation_zone
        if isinstance(selected_operation_zone, dict)
        else {}
    )
    return {
        "zone_id": _stripped_text(selected.get("zone_id")),
        "expected_revision": _int_or_default(selected.get("revision")),
        "boundary_json": boundary_json_from_vertices(
            boundary_vertices,
            frame_id=_frame_id_or_default(frame_id),
        ),
    }


def operation_zone_from_save_response(response):
    response = response if isinstance(response, dict) else {}
    operation_zone = response.get("operation_zone")
    return operation_zone if isinstance(operation_zone, dict) else None


def _frame_id_or_default(value, default="map"):
    frame_id = _stripped_text(value)
    return frame_id or default


def _int_or_default(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _stripped_text(value):
    return str(value or "").strip()


__all__ = [
    "OperationZoneEditorController",
    "build_operation_zone_boundary_save_payload",
    "build_operation_zone_save_payload",
    "operation_zone_from_save_response",
]
