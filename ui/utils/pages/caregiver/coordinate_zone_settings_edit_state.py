from dataclasses import dataclass


@dataclass(frozen=True)
class RowReplacement:
    rows: list
    selected_index: int


def replace_row_by_key(rows, updated_row, key):
    next_rows = list(rows if isinstance(rows, list) else [])
    updated = dict(updated_row if isinstance(updated_row, dict) else {})
    row_id = updated.get(key)

    for index, row in enumerate(next_rows):
        row = row if isinstance(row, dict) else {}
        if row.get(key) == row_id:
            next_rows[index] = updated
            return RowReplacement(rows=next_rows, selected_index=index)

    next_rows.append(updated)
    return RowReplacement(rows=next_rows, selected_index=len(next_rows) - 1)


def edit_save_enabled(
    *,
    selected_edit_type,
    expected_edit_type,
    dirty,
    map_loaded,
    save_thread,
):
    return (
        selected_edit_type == expected_edit_type
        and bool(dirty)
        and bool(map_loaded)
        and save_thread is None
    )


def edit_discard_enabled(*, selected_edit_type, expected_edit_type, dirty):
    return selected_edit_type == expected_edit_type and bool(dirty)


__all__ = [
    "RowReplacement",
    "edit_discard_enabled",
    "edit_save_enabled",
    "replace_row_by_key",
]
