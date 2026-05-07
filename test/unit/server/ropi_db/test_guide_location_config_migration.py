from server.ropi_db.guide_location_config_migration import (
    CONTROL_MAP_ID,
    MIGRATION_ID,
    SchemaState,
    build_guide_location_config_migration_steps,
)


def test_guide_location_config_migration_seeds_guide_goal_poses():
    state = SchemaState(
        existing_tables=frozenset({"map_profile", "operation_zone", "goal_pose"}),
    )

    steps = build_guide_location_config_migration_steps(state)
    by_name = {step.name: step for step in steps}

    assert [step.name for step in steps] == [
        "create_migration_history",
        "ensure_control_map_profile",
        "ensure_guide_operation_zones",
        "seed_guide_goal_poses",
        "record_migration",
    ]
    assert by_name["ensure_control_map_profile"].params == (
        CONTROL_MAP_ID,
        CONTROL_MAP_ID,
    )
    assert by_name["ensure_guide_operation_zones"].params == (
        CONTROL_MAP_ID,
        CONTROL_MAP_ID,
        CONTROL_MAP_ID,
    )
    assert by_name["seed_guide_goal_poses"].params == (
        CONTROL_MAP_ID,
        CONTROL_MAP_ID,
        CONTROL_MAP_ID,
    )
    assert "'guide_room_301', %s, 'room_301', 'GUIDE_DESTINATION'" in by_name[
        "seed_guide_goal_poses"
    ].sql
    assert "`pose_x`" not in by_name["seed_guide_goal_poses"].sql.split(
        "ON DUPLICATE KEY UPDATE",
        maxsplit=1,
    )[1]
    assert by_name["record_migration"].params == (MIGRATION_ID,)


def test_guide_location_config_migration_honors_applied_history_without_force():
    state = SchemaState(
        existing_tables=frozenset({"map_profile", "operation_zone", "goal_pose"}),
        migration_already_applied=True,
    )

    assert build_guide_location_config_migration_steps(state) == []

    forced_steps = build_guide_location_config_migration_steps(state, force=True)
    assert forced_steps[0].name == "create_migration_history"
    assert forced_steps[-1].params == (MIGRATION_ID,)
