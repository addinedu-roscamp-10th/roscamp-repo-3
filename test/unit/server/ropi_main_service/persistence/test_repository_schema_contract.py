from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[5]
REPOSITORY_ROOT = REPO_ROOT / "server" / "ropi_main_service" / "persistence" / "repositories"


def _source(filename: str) -> str:
    return (REPOSITORY_ROOT / filename).read_text(encoding="utf-8")


def test_repositories_do_not_reference_removed_tables_or_columns():
    combined_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(REPOSITORY_ROOT.glob("*.py"))
    )

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
    source = _source("inventory_repository.py")

    assert "FROM item" in source
    assert "UPDATE item" in source
    assert "item_id" in source
    assert "item_type" in source


def test_delivery_request_repository_persists_task_model():
    request_source = _source("task_request_repository.py")
    task_source = _source("delivery_task_repository.py")
    combined_source = request_source + "\n" + task_source

    assert "FROM item" in combined_source
    assert "INSERT INTO task" in combined_source
    assert "INSERT INTO delivery_task_item" in combined_source
    assert "INSERT INTO task_state_history" in combined_source
    assert "INSERT INTO task_event_log" in combined_source
    assert "assigned_robot_id" in combined_source


def test_member_event_repositories_use_member_event_table():
    for filename in (
        "patient_repository.py",
        "visitor_info_repository.py",
        "staff_call_repository.py",
        "visitor_register_repository.py",
        "visit_guide_repository.py",
    ):
        assert "member_event" in _source(filename)


def test_caregiver_repository_uses_task_and_runtime_status_tables():
    source = _source("caregiver_repository.py")

    assert "FROM task" in source
    assert "robot_runtime_status" in source
    assert "task_event_log" in source
