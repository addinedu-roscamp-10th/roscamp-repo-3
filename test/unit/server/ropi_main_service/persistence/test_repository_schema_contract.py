from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[5]
PERSISTENCE_ROOT = REPO_ROOT / "server" / "ropi_main_service" / "persistence"
REPOSITORY_ROOT = PERSISTENCE_ROOT / "repositories"
SQL_ROOT = PERSISTENCE_ROOT / "sql"


def _source(filename: str) -> str:
    return (REPOSITORY_ROOT / filename).read_text(encoding="utf-8")


def _sql_source(relative_path: str) -> str:
    return (SQL_ROOT / relative_path).read_text(encoding="utf-8")


def _combined_persistence_source() -> str:
    sources = [
        path.read_text(encoding="utf-8")
        for path in sorted(REPOSITORY_ROOT.glob("*.py"))
    ]
    sources.extend(
        path.read_text(encoding="utf-8")
        for path in sorted(SQL_ROOT.rglob("*.sql"))
    )
    return "\n".join(sources)


def test_repositories_do_not_reference_removed_tables_or_columns():
    combined_source = _combined_persistence_source()

    forbidden_tokens = (
        "FROM supply",
        "UPDATE supply",
        "supply_id",
        "supply_type",
        "INSERT INTO event",
        "FROM event\n",
        "JOIN event_type",
        "event_type_id",
        "FROM robot_event",
        "robot_event_id",
        "robot_event_type",
        "event_description",
    )

    for token in forbidden_tokens:
        assert token not in combined_source


def test_inventory_repository_uses_item_schema():
    source = "\n".join(
        (
            _source("inventory_repository.py"),
            _sql_source("inventory/list_items.sql"),
            _sql_source("inventory/add_quantity.sql"),
        )
    )

    assert "FROM item" in source
    assert "UPDATE item" in source
    assert "item_id" in source
    assert "item_type" in source


def test_delivery_request_repository_persists_task_model():
    combined_source = "\n".join(
        (
            _source("task_request_repository.py"),
            _source("delivery_task_repository.py"),
            _sql_source("task_request/list_items.sql"),
            _sql_source("delivery/insert_delivery_task.sql"),
            _sql_source("delivery/insert_delivery_task_item.sql"),
            _sql_source("delivery/insert_initial_task_history.sql"),
            _sql_source("delivery/insert_initial_task_event.sql"),
        )
    )

    assert "FROM item" in combined_source
    assert "INSERT INTO task" in combined_source
    assert "INSERT INTO delivery_task_item" in combined_source
    assert "INSERT INTO task_state_history" in combined_source
    assert "INSERT INTO task_event_log" in combined_source
    assert "assigned_robot_id" in combined_source


def test_member_event_repositories_use_member_event_table():
    source = "\n".join(
        (
            _source("task_request_repository.py"),
            _source("staff_call_repository.py"),
            _source("visitor_register_repository.py"),
            _source("visit_guide_repository.py"),
            _sql_source("member_event/insert_member_event.sql"),
            _sql_source("patient/recent_member_events.sql"),
            _sql_source("visitor_info/patient_visit_info.sql"),
        )
    )
    assert "member_event" in source
    assert "member_event" in _sql_source("visitor_info/patient_visit_info.sql")


def test_caregiver_repository_uses_task_and_runtime_status_tables():
    source = "\n".join(
        _sql_source(path)
        for path in (
            "caregiver/dashboard_summary.sql",
            "caregiver/robot_board.sql",
            "caregiver/timeline.sql",
            "caregiver/flow_board_events.sql",
        )
    )

    assert "FROM task" in source
    assert "robot_runtime_status" in source
    assert "task_event_log" in source
    assert "robot_manager_name" in source
    assert "fault_code" in source
    assert "last_seen_at" in source
