from server.ropi_db.fms_drive_runtime_schema_migration import (
    MIGRATION_ID,
    SchemaState,
    build_fms_drive_runtime_schema_migration_steps,
)


def test_fms_drive_runtime_schema_migration_creates_missing_runtime_tables():
    state = SchemaState(
        existing_tables=frozenset(
            {
                "map_profile",
                "robot",
                "task",
                "fms_waypoint",
                "fms_edge",
                "fms_route",
                "fms_route_waypoint",
            }
        )
    )

    steps = build_fms_drive_runtime_schema_migration_steps(state)
    by_name = {step.name: step for step in steps}

    assert steps[0].name == "create_migration_history"
    assert "create_drive_task_detail" in by_name
    assert "CREATE TABLE IF NOT EXISTS `drive_task_detail`" in by_name[
        "create_drive_task_detail"
    ].sql
    assert "CONSTRAINT `fk_drive_task_detail_route`" in by_name[
        "create_drive_task_detail"
    ].sql
    assert "create_fms_reservation" in by_name
    assert "CREATE TABLE IF NOT EXISTS `fms_reservation`" in by_name[
        "create_fms_reservation"
    ].sql
    assert "idx_fms_reservation_active_resource" in by_name[
        "create_fms_reservation"
    ].sql
    assert steps[-1].name == "record_migration"
    assert steps[-1].params == (MIGRATION_ID,)


def test_fms_drive_runtime_schema_migration_creates_missing_fms_graph_tables():
    state = SchemaState(existing_tables=frozenset({"map_profile", "robot", "task"}))

    step_names = [
        step.name for step in build_fms_drive_runtime_schema_migration_steps(state)
    ]

    assert step_names.index("create_fms_waypoint") < step_names.index(
        "create_fms_edge"
    )
    assert step_names.index("create_fms_route") < step_names.index(
        "create_fms_route_waypoint"
    )
    assert step_names.index("create_fms_route") < step_names.index(
        "create_drive_task_detail"
    )
    assert step_names.index("create_fms_edge") < step_names.index(
        "create_fms_reservation"
    )


def test_fms_drive_runtime_schema_migration_skips_current_tables():
    state = SchemaState(
        existing_tables=frozenset(
            {
                "map_profile",
                "robot",
                "task",
                "fms_waypoint",
                "fms_edge",
                "fms_route",
                "fms_route_waypoint",
                "drive_task_detail",
                "fms_reservation",
            }
        )
    )

    step_names = [
        step.name for step in build_fms_drive_runtime_schema_migration_steps(state)
    ]

    assert "create_drive_task_detail" not in step_names
    assert "create_fms_reservation" not in step_names
    assert step_names == ["create_migration_history", "record_migration"]


def test_fms_drive_runtime_schema_migration_honors_applied_history_without_force():
    state = SchemaState(migration_already_applied=True)

    assert build_fms_drive_runtime_schema_migration_steps(state) == []

    forced_steps = build_fms_drive_runtime_schema_migration_steps(state, force=True)
    assert forced_steps[0].name == "create_migration_history"
    assert forced_steps[-1].params == (MIGRATION_ID,)
