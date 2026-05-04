import pytest

from server.ropi_main_service.persistence.sql_loader import SQL_ROOT, load_sql


def test_load_sql_reads_query_file_under_sql_root():
    sql = load_sql("caregiver/dashboard_summary.sql")

    assert sql.startswith("SELECT")
    assert "robot_runtime_status" in sql
    assert "total_robot_count" in sql
    assert "warning_error_count" in sql
    assert "task_event_log" in sql


def test_load_sql_reads_all_repository_sql_files():
    for path in SQL_ROOT.rglob("*.sql"):
        relative_path = path.relative_to(SQL_ROOT).as_posix()
        assert load_sql(relative_path)


def test_load_sql_rejects_path_traversal():
    with pytest.raises(ValueError):
        load_sql("../config.py")


def test_load_sql_requires_sql_extension():
    with pytest.raises(ValueError):
        load_sql("caregiver/dashboard_summary.txt")
