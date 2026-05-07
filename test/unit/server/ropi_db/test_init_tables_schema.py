from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
INIT_TABLES_SQL = REPO_ROOT / "server" / "ropi_db" / "init_tables.sql"
INSERT_DUMMIES_SQL = REPO_ROOT / "server" / "ropi_db" / "insert_dummies.sql"
ROPI_DB_README = REPO_ROOT / "server" / "ropi_db" / "README.md"
PYPROJECT_TOML = REPO_ROOT / "pyproject.toml"


def _ddl() -> str:
    return INIT_TABLES_SQL.read_text(encoding="utf-8")


def _seed_sql() -> str:
    return INSERT_DUMMIES_SQL.read_text(encoding="utf-8")


def _db_readme() -> str:
    return ROPI_DB_README.read_text(encoding="utf-8")


def _pyproject() -> str:
    return PYPROJECT_TOML.read_text(encoding="utf-8")


def _sql(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_schema_uses_member_event_without_legacy_event_type_tables():
    ddl = _ddl()

    assert "CREATE TABLE `member_event`" in ddl
    assert "`member_event_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT" in ddl
    assert "`event_type_code` VARCHAR(50) NOT NULL" in ddl
    assert "`event_category` VARCHAR(30) NOT NULL" in ddl
    assert "`severity` VARCHAR(20) NOT NULL" in ddl
    assert "CREATE TABLE `event`" not in ddl
    assert "CREATE TABLE `event_type`" not in ddl


def test_schema_uses_item_table_and_unsigned_delivery_quantities():
    ddl = _ddl()

    assert "CREATE TABLE `item`" in ddl
    assert "`item_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT" in ddl
    assert "`item_type` VARCHAR(100) NOT NULL" in ddl
    assert "`quantity` INT UNSIGNED NOT NULL" in ddl
    assert "CREATE TABLE `supply`" not in ddl
    assert "`requested_quantity` INT UNSIGNED NOT NULL" in ddl
    assert "`loaded_quantity` INT UNSIGNED NOT NULL" in ddl
    assert "`delivered_quantity` INT UNSIGNED NOT NULL" in ddl


def test_dummy_item_seed_includes_food_example():
    seed_sql = _seed_sql()

    assert "(6, '식료품', '두유', 60, NOW(), NOW())" in seed_sql


def test_schema_contains_control_task_and_log_tables():
    ddl = _ddl()

    for table_name in (
        "ropi_schema_migration",
        "task",
        "delivery_task_detail",
        "delivery_task_item",
        "patrol_task_detail",
        "patrol_area",
        "guide_task_detail",
        "task_state_history",
        "task_event_log",
        "command_execution",
        "robot_runtime_status",
        "robot_data_log",
        "ai_inference_log",
        "stream_metrics_log",
        "idempotency_record",
        "kiosk_staff_call_log",
    ):
        assert f"CREATE TABLE `{table_name}`" in ddl

    assert "CREATE TABLE `robot_event`" not in ddl
    assert "CREATE TABLE `map_table`" not in ddl


def test_schema_migration_history_table_is_reset_with_schema_init():
    ddl = _ddl()

    assert "DROP TABLE IF EXISTS `ropi_schema_migration`;" in ddl
    assert "CREATE TABLE `ropi_schema_migration`" in ddl
    assert "`migration_id` VARCHAR(100) NOT NULL" in ddl
    assert "`applied_at` DATETIME NOT NULL" in ddl
    assert "CONSTRAINT `pk_ropi_schema_migration` PRIMARY KEY (`migration_id`)" in ddl


def test_ai_inference_log_uses_string_frame_id_for_pat_005():
    ddl = _ddl()

    ai_inference_section = ddl.split("CREATE TABLE `ai_inference_log`", 1)[1].split(
        "CREATE TABLE `stream_metrics_log`",
        1,
    )[0]

    assert "`frame_id` VARCHAR(100) NULL" in ai_inference_section
    assert "`frame_id` BIGINT UNSIGNED" not in ai_inference_section


def test_patrol_schema_separates_area_from_operation_zone():
    ddl = _ddl()
    seed_sql = _seed_sql()

    assert "CREATE TABLE `patrol_area`" in ddl
    assert "`patrol_area_id` VARCHAR(100) NOT NULL" in ddl
    assert "`path_json` JSON NOT NULL" in ddl
    assert "`patrol_area_id` VARCHAR(100) NOT NULL" in ddl
    assert "`patrol_area_revision` INT UNSIGNED NOT NULL" in ddl
    assert "`path_snapshot_json` JSON NOT NULL" in ddl
    assert "`waypoint_count` INT UNSIGNED NOT NULL DEFAULT 0" in ddl
    assert "`current_waypoint_index` INT UNSIGNED NULL" in ddl
    assert "CONSTRAINT `fk_patrol_task_detail_patrol_area`" in ddl
    assert "CREATE TABLE `patrol_task_zone`" not in ddl
    assert "`coverage_strategy`" not in ddl

    operation_zone_section = ddl.split("CREATE TABLE `operation_zone`", 1)[1].split(
        "CREATE TABLE `patrol_area`",
        1,
    )[0]
    assert "`path_json`" not in operation_zone_section
    assert "`default_robot_id`" not in operation_zone_section

    assert "INSERT INTO `patrol_area`" in seed_sql
    assert "INSERT INTO `operation_zone`" in seed_sql
    assert "`path_json`" in seed_sql
    assert "`default_robot_id`" not in seed_sql

    assert "polygon_json" not in ddl
    assert "polygon_json" not in seed_sql
    assert "coverage_polygon_snapshot_json" not in ddl
    assert "coverage_polygon_snapshot_json" not in seed_sql


def test_operation_zone_does_not_store_patrol_robot_hint():
    ddl = _ddl()
    seed_sql = _seed_sql()

    assert "`default_robot_id` VARCHAR(50) NULL" not in ddl
    assert "CONSTRAINT `fk_operation_zone_default_robot`" not in ddl
    assert "idx_operation_zone_default_robot" not in ddl
    assert "`default_robot_id`" not in seed_sql


def test_operation_zone_supports_optional_boundary_polygon():
    ddl = _ddl()
    seed_sql = _seed_sql()

    operation_zone_section = ddl.split("CREATE TABLE `operation_zone`", 1)[1].split(
        "CREATE TABLE `patrol_area`",
        1,
    )[0]

    assert "`boundary_json` JSON NULL" in operation_zone_section
    assert "`boundary_json`" in seed_sql
    assert '"type":"POLYGON"' in seed_sql
    assert '"vertices"' in seed_sql
    assert '"frame_id":"map"' in seed_sql
    assert "`path_json`" not in operation_zone_section


def test_operation_zone_identity_is_scoped_by_map():
    ddl = _ddl()

    operation_zone_section = ddl.split("CREATE TABLE `operation_zone`", 1)[1].split(
        "CREATE TABLE `patrol_area`",
        1,
    )[0]
    goal_pose_section = ddl.split("CREATE TABLE `goal_pose`", 1)[1].split(
        "CREATE TABLE `fms_waypoint`",
        1,
    )[0]

    assert (
        "CONSTRAINT `pk_operation_zone` PRIMARY KEY (`map_id`, `zone_id`)"
        in operation_zone_section
    )
    assert "CONSTRAINT `fk_goal_pose_operation_zone`" in goal_pose_section
    assert "FOREIGN KEY (`map_id`, `zone_id`)" in goal_pose_section
    assert "REFERENCES `operation_zone` (`map_id`, `zone_id`)" in goal_pose_section
    assert "FOREIGN KEY (`zone_id`)" not in goal_pose_section


def test_dummy_goal_pose_seed_maps_delivery_team_coordinates_to_operator_ids():
    seed_sql = _seed_sql()

    assert "delivery_room_301" in seed_sql
    assert "room2" not in seed_sql
    assert (
        "'device/ropi_mobile/src/ropi_nav_config/maps/map_test12_0506.yaml'" in seed_sql
    )
    assert (
        "'device/ropi_mobile/src/ropi_nav_config/maps/map_test12_0506.pgm'" in seed_sql
    )
    assert "('room_301', 'map_0504', '301호', 'ROOM'," in seed_sql
    assert "('room_301', 'map_test12_0506', '301호', 'ROOM'," in seed_sql
    assert (
        "('pickup_supply', 'map_test12_0506', 'supply_station', 'PICKUP', 0.64, -0.44, 3.141592653589793,"
        in seed_sql
    )
    assert (
        "('delivery_room_301', 'map_test12_0506', 'room_301', 'DESTINATION', 1.6838363409042358, -0.4915957748889923, 1.5707963267948966,"
        in seed_sql
    )
    assert (
        "('dock_home', 'map_test12_0506', 'dock', 'DOCK', -0.009538442827761173, -0.006931785028427839, 0.0,"
        in seed_sql
    )


def test_db_runbook_documents_multimap_coordinate_migration_cli():
    readme = _db_readme()
    pyproject = _pyproject()

    assert (
        'ropi-db-migrate-multimap = "server.ropi_db.multimap_coordinate_migration:main"'
        in pyproject
    )
    assert "uv run ropi-db-migrate-multimap" in readme
    assert "uv run ropi-db-migrate-multimap --apply" in readme
    assert "`operation_zone` primary key를 `(map_id, zone_id)`로 보정" in readme
    assert "`goal_pose(map_id, zone_id)` -> `operation_zone(map_id, zone_id)`" in readme


def test_goal_pose_queries_join_operation_zone_by_map_and_zone():
    for relative_path in (
        "server/ropi_main_service/persistence/sql/coordinate_config/find_goal_pose.sql",
        "server/ropi_main_service/persistence/sql/coordinate_config/list_goal_poses.sql",
        "server/ropi_main_service/persistence/sql/task_request/list_delivery_destinations.sql",
        "server/ropi_main_service/persistence/sql/task_request/list_enabled_goal_poses.sql",
        "server/ropi_main_service/persistence/sql/guide/find_destination_goal_pose.sql",
    ):
        sql = _sql(relative_path)
        assert "ON oz.map_id = gp.map_id" in sql
        assert "AND oz.zone_id = gp.zone_id" in sql


def test_dummy_patrol_area_contains_path_backed_route():
    seed_sql = _seed_sql()

    assert "INSERT INTO `patrol_area`" in seed_sql
    assert "patrol_ward_night_01" in seed_sql
    assert "야간 병동 순찰" in seed_sql
    assert '"poses"' in seed_sql


def test_schema_contains_expected_indexes():
    ddl = _ddl()

    expected_indexes = (
        "idx_member_event_member_event_at",
        "idx_member_event_type_event_at",
        "idx_task_status_type_created_at",
        "idx_task_robot_status_updated_at",
        "idx_task_requester_created_at",
        "idx_delivery_task_item_task",
        "idx_delivery_task_item_item",
        "idx_patrol_area_map_enabled_name",
        "idx_patrol_task_detail_area_revision",
        "idx_task_state_history_task_changed_at",
        "idx_task_event_log_task_occurred_at",
        "idx_command_execution_task_started_at",
        "idx_command_execution_robot_started_at",
        "idx_robot_data_log_robot_received_at",
        "idx_robot_data_log_task_received_at",
        "idx_stream_metrics_robot_window",
        "idx_ai_inference_task_inferred_at",
        "idx_kiosk_staff_call_created_at",
        "uq_idempotency",
        "uq_kiosk_staff_call_idempotency",
    )

    for index_name in expected_indexes:
        assert index_name in ddl


def test_kiosk_staff_call_log_supports_unlinked_lobby_calls():
    ddl = _ddl()

    section = ddl.split("CREATE TABLE `kiosk_staff_call_log`", 1)[1].split(
        "CREATE TABLE `idempotency_record`",
        1,
    )[0]

    assert "`visitor_id` BIGINT UNSIGNED NULL" in section
    assert "`member_id` BIGINT UNSIGNED NULL" in section
    assert "`kiosk_id` VARCHAR(100) NULL" in section
    assert "CONSTRAINT `fk_kiosk_staff_call_visitor`" in section
    assert "CONSTRAINT `fk_kiosk_staff_call_member`" in section


def test_robot_schema_does_not_add_capability_or_station_assignment_tables():
    ddl = _ddl()
    seed_sql = _seed_sql()

    assert "CREATE TABLE `robot_capability`" not in ddl
    assert "CREATE TABLE `robot_station_assignment`" not in ddl
    assert "INSERT INTO `robot_capability`" not in seed_sql
    assert "INSERT INTO `robot_station_assignment`" not in seed_sql


def test_dummy_robot_seed_does_not_encode_fixed_pinky_scenario_roles():
    seed_sql = _seed_sql()

    assert "('pinky1', 'Pinky Pro', '192.168.0.101',\n 'IDLE', '모바일팀'" in seed_sql
    assert "('pinky2', 'Pinky Pro', '192.168.0.102',\n 'IDLE', '모바일팀'" in seed_sql
    assert "('pinky3', 'Pinky Pro', '192.168.0.103',\n 'IDLE', '모바일팀'" in seed_sql
    assert "('pinky1', 'Pinky Pro', '192.168.0.101',\n 'IDLE', '안내팀'" not in seed_sql
    assert "('pinky2', 'Pinky Pro', '192.168.0.102',\n 'IDLE', '운반팀'" not in seed_sql
    assert "('pinky3', 'Pinky Pro', '192.168.0.103',\n 'IDLE', '순찰팀'" not in seed_sql


def test_dummy_data_targets_current_schema_tables():
    seed_sql = _seed_sql()

    for table_name in (
        "member",
        "caregiver",
        "visitor",
        "preference",
        "prescription",
        "member_event",
        "robot",
        "item",
        "map_profile",
        "operation_zone",
        "patrol_area",
        "goal_pose",
        "task",
        "delivery_task_detail",
        "delivery_task_item",
        "task_state_history",
        "task_event_log",
        "command_execution",
        "robot_runtime_status",
    ):
        assert f"INSERT INTO `{table_name}`" in seed_sql

    assert "INSERT INTO `event`" not in seed_sql
    assert "INSERT INTO `event_type`" not in seed_sql
    assert "INSERT INTO `robot_event`" not in seed_sql
    assert "INSERT INTO `supply`" not in seed_sql
    assert "INSERT INTO `map_table`" not in seed_sql


def test_dummy_data_does_not_force_database_name():
    seed_sql = _seed_sql()

    assert "USE care_service" not in seed_sql
