from server.ropi_db.fms_conflict_zone_schema_migration import (
    MIGRATION_ID,
    SchemaState,
    build_fms_conflict_zone_schema_migration_steps,
)


def test_fms_conflict_zone_schema_migration_creates_missing_schema():
    state = SchemaState(
        existing_tables=frozenset(
            {
                "ropi_schema_migration",
                "map_profile",
                "fms_edge",
                "fms_reservation",
            }
        ),
        existing_columns={
            "fms_reservation": frozenset(
                {
                    "reservation_id",
                    "resource_type",
                    "resource_id",
                    "waypoint_id",
                    "edge_id",
                }
            )
        },
    )

    steps = build_fms_conflict_zone_schema_migration_steps(state)
    step_names = [step.name for step in steps]
    by_name = {step.name: step for step in steps}

    assert step_names[0] == "create_migration_history"
    assert step_names.index("create_fms_conflict_zone") < step_names.index(
        "create_fms_edge_conflict_zone"
    )
    assert "CREATE TABLE IF NOT EXISTS `fms_conflict_zone`" in by_name[
        "create_fms_conflict_zone"
    ].sql
    assert "CREATE TABLE IF NOT EXISTS `fms_edge_conflict_zone`" in by_name[
        "create_fms_edge_conflict_zone"
    ].sql
    assert "add_fms_reservation_conflict_zone_id" in by_name
    assert "ADD COLUMN `conflict_zone_id` VARCHAR(100) NULL" in by_name[
        "add_fms_reservation_conflict_zone_id"
    ].sql
    assert "add_fms_reservation_conflict_zone_fk" in by_name
    assert steps[-1].name == "record_migration"
    assert steps[-1].params == (MIGRATION_ID,)


def test_fms_conflict_zone_schema_migration_skips_current_schema():
    state = SchemaState(
        existing_tables=frozenset(
            {
                "ropi_schema_migration",
                "map_profile",
                "fms_edge",
                "fms_conflict_zone",
                "fms_edge_conflict_zone",
                "fms_reservation",
            }
        ),
        existing_columns={"fms_reservation": frozenset({"conflict_zone_id"})},
        existing_constraints=frozenset({"fk_fms_reservation_conflict_zone"}),
    )

    steps = build_fms_conflict_zone_schema_migration_steps(state)

    assert [step.name for step in steps] == [
        "create_migration_history",
        "record_migration",
    ]


def test_fms_conflict_zone_schema_migration_honors_applied_history_without_force():
    state = SchemaState(migration_already_applied=True)

    assert build_fms_conflict_zone_schema_migration_steps(state) == []

    forced_steps = build_fms_conflict_zone_schema_migration_steps(state, force=True)
    assert forced_steps[0].name == "create_migration_history"
    assert forced_steps[-1].params == (MIGRATION_ID,)
