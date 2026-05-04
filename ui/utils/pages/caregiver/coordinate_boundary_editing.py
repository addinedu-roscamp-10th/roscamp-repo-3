from dataclasses import dataclass

from ui.utils.pages.caregiver.coordinate_pose_editing import (
    coerce_point2d,
    delete_index,
    replace_index,
)


@dataclass(frozen=True)
class BoundaryEdit:
    vertices: list
    selected_index: int | None


def boundary_vertices_from_json(boundary_json):
    boundary = boundary_json if isinstance(boundary_json, dict) else {}
    raw_vertices = boundary.get("vertices")
    if not isinstance(raw_vertices, list):
        return []
    return [
        {
            "x": _float_or_default(vertex.get("x")),
            "y": _float_or_default(vertex.get("y")),
        }
        for vertex in raw_vertices
        if isinstance(vertex, dict)
    ]


def append_boundary_vertex(vertices, world_pose):
    vertex = coerce_point2d(world_pose)
    if vertex is None:
        return None
    next_vertices = [
        dict(row) if isinstance(row, dict) else row for row in vertices or []
    ]
    next_vertices.append(vertex)
    return BoundaryEdit(vertices=next_vertices, selected_index=len(next_vertices) - 1)


def replace_selected_boundary_vertex(vertices, selected_index, *, x, y):
    try:
        next_vertex = {
            "x": float(x),
            "y": float(y),
        }
    except (TypeError, ValueError):
        return None
    next_vertices = replace_index(vertices, selected_index, next_vertex)
    if next_vertices is None:
        return None
    return BoundaryEdit(vertices=next_vertices, selected_index=int(selected_index))


def delete_selected_boundary_vertex(vertices, selected_index):
    deleted = delete_index(vertices, selected_index)
    if deleted is None:
        return None
    next_vertices, next_index = deleted
    return BoundaryEdit(vertices=next_vertices, selected_index=next_index)


def clear_boundary_vertices(vertices):
    if not vertices:
        return None
    return BoundaryEdit(vertices=[], selected_index=None)


def move_selected_boundary_vertex_to_world(vertices, selected_index, world_pose):
    vertex = coerce_point2d(world_pose)
    if vertex is None:
        return None
    next_vertices = replace_index(vertices, selected_index, vertex)
    if next_vertices is None:
        return None
    return BoundaryEdit(vertices=next_vertices, selected_index=int(selected_index))


def selected_boundary_vertex(vertices, selected_index):
    if not _valid_index(vertices, selected_index):
        return None
    row = vertices[int(selected_index)]
    return row if isinstance(row, dict) else None


def boundary_vertex_buttons_state(vertices, selected_index):
    has_selection = selected_boundary_vertex(vertices, selected_index) is not None
    return {
        "delete": has_selection,
        "clear": bool(vertices),
    }


def boundary_table_rows(vertices):
    return [
        [
            str(row_index + 1),
            _number_text(vertex.get("x")),
            _number_text(vertex.get("y")),
        ]
        for row_index, vertex in enumerate(vertices or [])
        if isinstance(vertex, dict)
    ]


def boundary_json_from_vertices(vertices, *, frame_id):
    payload_vertices = boundary_payload_vertices(vertices)
    if not payload_vertices:
        return None
    return {
        "type": "POLYGON",
        "header": {"frame_id": str(frame_id or "map")},
        "vertices": payload_vertices,
    }


def boundary_payload_vertices(vertices):
    return [
        {
            "x": _float_or_default(vertex.get("x")),
            "y": _float_or_default(vertex.get("y")),
        }
        for vertex in vertices or []
        if isinstance(vertex, dict)
    ]


def _valid_index(rows, index):
    try:
        index = int(index)
    except (TypeError, ValueError):
        return False
    return 0 <= index < len(rows or [])


def _float_or_default(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _number_text(value):
    return f"{_float_or_default(value):.4f}"


__all__ = [
    "BoundaryEdit",
    "append_boundary_vertex",
    "boundary_json_from_vertices",
    "boundary_payload_vertices",
    "boundary_table_rows",
    "boundary_vertex_buttons_state",
    "boundary_vertices_from_json",
    "clear_boundary_vertices",
    "delete_selected_boundary_vertex",
    "move_selected_boundary_vertex_to_world",
    "replace_selected_boundary_vertex",
    "selected_boundary_vertex",
]
