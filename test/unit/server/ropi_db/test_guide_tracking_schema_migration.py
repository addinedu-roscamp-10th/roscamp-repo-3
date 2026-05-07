from server.ropi_db.guide_tracking_schema_migration import (
    MIGRATION_ID,
    SchemaState,
    build_guide_tracking_schema_migration_steps,
)


def test_guide_tracking_schema_migration_plans_varchar_to_int_conversion():
    state = SchemaState(
        existing_tables=frozenset({"guide_task_detail"}),
        target_track_id_data_type="varchar",
    )

    steps = build_guide_tracking_schema_migration_steps(state)
    by_name = {step.name: step for step in steps}

    assert [step.name for step in steps] == [
        "create_migration_history",
        "normalize_legacy_target_track_id",
        "alter_target_track_id_int",
        "record_migration",
    ]
    assert "NOT REGEXP" in by_name["normalize_legacy_target_track_id"].sql
    assert "MODIFY `target_track_id` INT NULL" in by_name[
        "alter_target_track_id_int"
    ].sql
    assert by_name["record_migration"].params == (MIGRATION_ID,)


def test_guide_tracking_schema_migration_skips_alter_when_already_int():
    state = SchemaState(
        existing_tables=frozenset({"guide_task_detail"}),
        target_track_id_data_type="int",
    )

    step_names = [
        step.name for step in build_guide_tracking_schema_migration_steps(state)
    ]

    assert "normalize_legacy_target_track_id" not in step_names
    assert "alter_target_track_id_int" not in step_names
    assert step_names == ["create_migration_history", "record_migration"]


def test_guide_tracking_schema_migration_honors_applied_history_without_force():
    state = SchemaState(
        existing_tables=frozenset({"guide_task_detail"}),
        target_track_id_data_type="varchar",
        migration_already_applied=True,
    )

    assert build_guide_tracking_schema_migration_steps(state) == []

    forced_steps = build_guide_tracking_schema_migration_steps(state, force=True)
    assert forced_steps[0].name == "create_migration_history"
    assert forced_steps[-1].params == (MIGRATION_ID,)
