def test_boundary_vertices_from_json_normalizes_vertices():
    from ui.utils.pages.caregiver.coordinate_boundary_editing import (
        boundary_vertices_from_json,
    )

    assert boundary_vertices_from_json(
        {
            "type": "POLYGON",
            "vertices": [
                {"x": "0.1", "y": 0.2},
                "invalid",
                {"x": None, "y": "bad"},
            ],
        }
    ) == [
        {"x": 0.1, "y": 0.2},
        {"x": 0.0, "y": 0.0},
    ]


def test_boundary_table_rows_format_vertex_values():
    from ui.utils.pages.caregiver.coordinate_boundary_editing import (
        boundary_table_rows,
    )

    assert boundary_table_rows(
        [
            {"x": 0, "y": 0.2},
            {"x": 1.23456, "y": None},
        ]
    ) == [
        ["1", "0.0000", "0.2000"],
        ["2", "1.2346", "0.0000"],
    ]


def test_replace_and_move_selected_boundary_vertex():
    from ui.utils.pages.caregiver.coordinate_boundary_editing import (
        move_selected_boundary_vertex_to_world,
        replace_selected_boundary_vertex,
    )

    vertices = [
        {"x": 0.0, "y": 0.0},
        {"x": 1.0, "y": 0.0},
        {"x": 1.0, "y": 1.0},
    ]

    replaced = replace_selected_boundary_vertex(vertices, 1, x=0.5, y=0.25)
    assert replaced is not None
    assert replaced.selected_index == 1
    assert replaced.vertices[1] == {"x": 0.5, "y": 0.25}

    moved = move_selected_boundary_vertex_to_world(
        replaced.vertices,
        1,
        {"x": 0.75, "y": 0.5},
    )
    assert moved is not None
    assert moved.selected_index == 1
    assert moved.vertices[1] == {"x": 0.75, "y": 0.5}


def test_append_delete_clear_and_buttons_state():
    from ui.utils.pages.caregiver.coordinate_boundary_editing import (
        append_boundary_vertex,
        boundary_vertex_buttons_state,
        clear_boundary_vertices,
        delete_selected_boundary_vertex,
    )

    edit = append_boundary_vertex([{"x": 0.0, "y": 0.0}], {"x": 1.0, "y": 0.0})
    assert edit is not None
    assert edit.selected_index == 1
    assert edit.vertices == [{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 0.0}]
    assert boundary_vertex_buttons_state(edit.vertices, edit.selected_index) == {
        "delete": True,
        "clear": True,
    }

    deleted = delete_selected_boundary_vertex(edit.vertices, edit.selected_index)
    assert deleted is not None
    assert deleted.selected_index == 0
    assert deleted.vertices == [{"x": 0.0, "y": 0.0}]

    cleared = clear_boundary_vertices(deleted.vertices)
    assert cleared is not None
    assert cleared.selected_index is None
    assert cleared.vertices == []
    assert boundary_vertex_buttons_state(cleared.vertices, cleared.selected_index) == {
        "delete": False,
        "clear": False,
    }


def test_boundary_json_from_vertices_returns_full_polygon_or_none():
    from ui.utils.pages.caregiver.coordinate_boundary_editing import (
        boundary_json_from_vertices,
    )

    assert boundary_json_from_vertices([], frame_id="map") is None
    assert boundary_json_from_vertices(
        [
            {"x": "0.0", "y": "0.0"},
            {"x": 1.0, "y": 0.0},
            {"x": 1.0, "y": None},
        ],
        frame_id="map",
    ) == {
        "type": "POLYGON",
        "header": {"frame_id": "map"},
        "vertices": [
            {"x": 0.0, "y": 0.0},
            {"x": 1.0, "y": 0.0},
            {"x": 1.0, "y": 0.0},
        ],
    }
