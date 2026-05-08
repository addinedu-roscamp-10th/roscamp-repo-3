from server.ropi_db.multimap_coordinate_migration import (
    CONTROL_MAP_ID,
    MIGRATION_ID,
    OLD_MAP_ID,
    TRANSPORT_MAP_ID,
    ForeignKeyConstraint,
    SchemaState,
    build_multimap_coordinate_migration_steps,
)


def _old_schema_state():
    return SchemaState(
        existing_tables=frozenset(
            {
                "map_profile",
                "operation_zone",
                "goal_pose",
                "patrol_area",
                "task",
            }
        ),
        operation_zone_primary_key=("zone_id",),
        goal_pose_operation_zone_foreign_keys=(
            ForeignKeyConstraint(
                name="fk_goal_pose_operation_zone",
                columns=("zone_id",),
                referenced_table="operation_zone",
                referenced_columns=("zone_id",),
            ),
        ),
        goal_pose_indexes=(
            ("PRIMARY", ("goal_pose_id",)),
            ("idx_goal_pose_map_purpose", ("map_id", "purpose")),
        ),
    )


def test_multimap_coordinate_migration_plans_schema_conversion_for_old_db():
    steps = build_multimap_coordinate_migration_steps(_old_schema_state())
    step_names = [step.name for step in steps]

    assert step_names.index(
        "drop_outdated_goal_pose_fk_fk_goal_pose_operation_zone"
    ) < (step_names.index("drop_operation_zone_primary_key"))
    assert step_names.index("add_operation_zone_composite_primary_key") < (
        step_names.index("seed_transport_operation_zones")
    )
    assert step_names.index("seed_transport_goal_poses") < (
        step_names.index("add_goal_pose_operation_zone_composite_fk")
    )
    assert "add_goal_pose_map_zone_index" in step_names
    assert step_names[-1] == "record_migration"


def test_multimap_coordinate_migration_remaps_old_map_references():
    steps = build_multimap_coordinate_migration_steps(_old_schema_state())
    by_name = {step.name: step for step in steps}

    assert by_name["remap_old_operation_zones_to_control_map"].params == (
        CONTROL_MAP_ID,
        OLD_MAP_ID,
    )
    assert by_name["remap_old_patrol_areas_to_control_map"].params == (
        CONTROL_MAP_ID,
        OLD_MAP_ID,
    )
    assert by_name["remap_old_transport_goal_poses_to_transport_map"].params == (
        TRANSPORT_MAP_ID,
        OLD_MAP_ID,
    )
    assert by_name["remap_old_task_maps"].params == (
        TRANSPORT_MAP_ID,
        CONTROL_MAP_ID,
        OLD_MAP_ID,
    )
    assert by_name["delete_retired_old_map_profile"].params == (OLD_MAP_ID,)


def test_multimap_coordinate_migration_seeds_transport_goal_pose_contract():
    steps = build_multimap_coordinate_migration_steps(_old_schema_state())
    seed_step = {step.name: step for step in steps}["seed_transport_goal_poses"]

    assert seed_step.params == (
        TRANSPORT_MAP_ID,
        TRANSPORT_MAP_ID,
        TRANSPORT_MAP_ID,
        TRANSPORT_MAP_ID,
        TRANSPORT_MAP_ID,
    )
    assert "('pickup_supply', %s, 'supply_station', 'PICKUP', 0.64, -0.44" in (
        seed_step.sql
    )
    assert (
        "'delivery_room_301', %s, 'room_301', 'DESTINATION', "
        "1.6838363409042358" in seed_step.sql
    )
    assert "'dock_home', %s, 'dock', 'DOCK', -0.009538442827761173" in seed_step.sql


def test_multimap_coordinate_migration_skips_schema_steps_when_already_current():
    state = SchemaState(
        existing_tables=frozenset({"map_profile", "operation_zone", "goal_pose"}),
        operation_zone_primary_key=("map_id", "zone_id"),
        goal_pose_operation_zone_foreign_keys=(
            ForeignKeyConstraint(
                name="fk_goal_pose_operation_zone",
                columns=("map_id", "zone_id"),
                referenced_table="operation_zone",
                referenced_columns=("map_id", "zone_id"),
            ),
        ),
        goal_pose_indexes=(("idx_goal_pose_map_zone", ("map_id", "zone_id")),),
    )

    step_names = [
        step.name for step in build_multimap_coordinate_migration_steps(state)
    ]

    assert "drop_operation_zone_primary_key" not in step_names
    assert "add_operation_zone_composite_primary_key" not in step_names
    assert "add_goal_pose_map_zone_index" not in step_names
    assert "add_goal_pose_operation_zone_composite_fk" not in step_names


def test_multimap_coordinate_migration_honors_applied_history_without_force():
    state = SchemaState(migration_already_applied=True)

    assert build_multimap_coordinate_migration_steps(state) == []

    forced_steps = build_multimap_coordinate_migration_steps(state, force=True)
    assert forced_steps[0].name == "create_migration_history"
    assert forced_steps[-1].params == (MIGRATION_ID,)
