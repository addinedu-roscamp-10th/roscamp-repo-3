from dataclasses import dataclass

from ui.utils.pages.caregiver.coordinate_waypoint_editing import (
    patrol_path_payload_poses,
)


@dataclass
class PatrolAreaEditorController:
    selected_row: dict | None = None
    selected_index: int | None = None
    selected_waypoint_index: int | None = None
    mode: str | None = None
    dirty: bool = False
    syncing_area_form: bool = False
    syncing_waypoint_form: bool = False

    def select(self, row_index, rows):
        row_index = int(row_index)
        row = rows[row_index]
        selected = dict(row if isinstance(row, dict) else {})
        self.selected_row = selected
        self.selected_index = row_index
        self.selected_waypoint_index = None
        self.mode = "edit"
        self.dirty = False
        return selected

    def start_create(self, *, frame_id):
        self.selected_row = None
        self.selected_index = None
        self.selected_waypoint_index = None
        self.mode = "create"
        self.dirty = False
        return {
            "patrol_area_id": "",
            "patrol_area_name": "",
            "revision": 0,
            "path_json": {
                "header": {"frame_id": _frame_id_or_default(frame_id)},
                "poses": [],
            },
            "is_enabled": True,
        }

    def mark_dirty(self, *, selected_edit_type):
        if (
            self.syncing_area_form
            or self.syncing_waypoint_form
            or selected_edit_type != "patrol_area"
        ):
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
        self.selected_waypoint_index = None
        self.mode = None
        self.dirty = False
        self.syncing_area_form = False
        self.syncing_waypoint_form = False


def build_patrol_area_path_save_payload(
    *,
    selected_patrol_area,
    patrol_area_id,
    frame_id,
    waypoints,
):
    selected = selected_patrol_area if isinstance(selected_patrol_area, dict) else {}
    return {
        "patrol_area_id": str(patrol_area_id or "").strip(),
        "expected_revision": _int_or_default(selected.get("revision")),
        "path_json": {
            "header": {"frame_id": _frame_id_or_default(frame_id)},
            "poses": patrol_path_payload_poses(waypoints),
        },
    }


def build_patrol_area_save_payload(
    *,
    mode,
    selected_patrol_area,
    patrol_area_id,
    patrol_area_name,
    frame_id,
    waypoints,
    is_enabled,
):
    payload = {
        "patrol_area_id": str(patrol_area_id or "").strip(),
        "patrol_area_name": str(patrol_area_name or "").strip(),
        "path_json": {
            "header": {"frame_id": _frame_id_or_default(frame_id)},
            "poses": patrol_path_payload_poses(waypoints),
        },
        "is_enabled": bool(is_enabled),
    }
    if str(mode or "").strip() != "create":
        selected = (
            selected_patrol_area
            if isinstance(selected_patrol_area, dict)
            else {}
        )
        payload["expected_revision"] = _int_or_default(selected.get("revision"))
    return payload


def patrol_area_from_path_save_response(response):
    response = response if isinstance(response, dict) else {}
    patrol_area = response.get("patrol_area")
    return patrol_area if isinstance(patrol_area, dict) else None


def patrol_area_from_save_response(response):
    return patrol_area_from_path_save_response(response)


def patrol_path_poses_from_save_payload(payload):
    payload = payload if isinstance(payload, dict) else {}
    path_json = payload.get("path_json")
    path_json = path_json if isinstance(path_json, dict) else {}
    poses = path_json.get("poses")
    return poses if isinstance(poses, list) else []


def _frame_id_or_default(value, default="map"):
    frame_id = str(value or "").strip()
    return frame_id or default


def _int_or_default(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


__all__ = [
    "PatrolAreaEditorController",
    "build_patrol_area_save_payload",
    "build_patrol_area_path_save_payload",
    "patrol_area_from_save_response",
    "patrol_area_from_path_save_response",
    "patrol_path_poses_from_save_payload",
]
