import argparse
from dataclasses import dataclass

from server.ropi_main_service.persistence.connection import get_connection


MIGRATION_ID = "20260526_fms_drive_runtime_schema"


@dataclass(frozen=True)
class MigrationStep:
    name: str
    sql: str
    params: tuple = ()

    def preview(self) -> str:
        if not self.params:
            return self.sql
        return f"{self.sql}\n-- params: {self.params!r}"


@dataclass(frozen=True)
class SchemaState:
    existing_tables: frozenset[str] = frozenset()
    migration_already_applied: bool = False


def build_fms_drive_runtime_schema_migration_steps(
    state: SchemaState,
    *,
    force=False,
) -> list[MigrationStep]:
    if state.migration_already_applied and not force:
        return []

    steps = [_create_migration_history_step()]
    effective_tables = set(state.existing_tables)

    if "map_profile" in effective_tables:
        for table_name, step_factory in (
            ("fms_waypoint", _create_fms_waypoint_step),
            ("fms_edge", _create_fms_edge_step),
            ("fms_route", _create_fms_route_step),
            ("fms_route_waypoint", _create_fms_route_waypoint_step),
        ):
            if table_name not in effective_tables:
                steps.append(step_factory())
                effective_tables.add(table_name)

    if {"task", "fms_route"}.issubset(effective_tables):
        if "drive_task_detail" not in effective_tables:
            steps.append(_create_drive_task_detail_step())
            effective_tables.add("drive_task_detail")

    if {"task", "robot", "map_profile", "fms_waypoint", "fms_edge"}.issubset(
        effective_tables
    ):
        if "fms_reservation" not in effective_tables:
            steps.append(_create_fms_reservation_step())
            effective_tables.add("fms_reservation")

    steps.append(_record_migration_step())
    return steps


def _create_migration_history_step() -> MigrationStep:
    return MigrationStep(
        "create_migration_history",
        """
CREATE TABLE IF NOT EXISTS `ropi_schema_migration` (
    `migration_id` VARCHAR(100) NOT NULL,
    `applied_at` DATETIME NOT NULL,
    CONSTRAINT `pk_ropi_schema_migration` PRIMARY KEY (`migration_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""".strip(),
    )


def _create_fms_waypoint_step() -> MigrationStep:
    return MigrationStep(
        "create_fms_waypoint",
        """
CREATE TABLE IF NOT EXISTS `fms_waypoint` (
    `waypoint_id` VARCHAR(100) NOT NULL,
    `map_id` VARCHAR(100) NOT NULL,
    `display_name` VARCHAR(100) NOT NULL,
    `waypoint_type` VARCHAR(50) NOT NULL,
    `pose_x` DOUBLE NOT NULL,
    `pose_y` DOUBLE NOT NULL,
    `pose_yaw` DOUBLE NOT NULL,
    `frame_id` VARCHAR(50) NOT NULL DEFAULT 'map',
    `snap_group` VARCHAR(100) NULL,
    `is_enabled` BOOLEAN NOT NULL DEFAULT TRUE,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    CONSTRAINT `pk_fms_waypoint` PRIMARY KEY (`waypoint_id`),
    CONSTRAINT `fk_fms_waypoint_map_profile`
        FOREIGN KEY (`map_id`)
        REFERENCES `map_profile` (`map_id`),
    KEY `idx_fms_waypoint_map_enabled_name`
        (`map_id`, `is_enabled`, `display_name`),
    KEY `idx_fms_waypoint_map_type`
        (`map_id`, `waypoint_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""".strip(),
    )


def _create_fms_edge_step() -> MigrationStep:
    return MigrationStep(
        "create_fms_edge",
        """
CREATE TABLE IF NOT EXISTS `fms_edge` (
    `edge_id` VARCHAR(100) NOT NULL,
    `map_id` VARCHAR(100) NOT NULL,
    `from_waypoint_id` VARCHAR(100) NOT NULL,
    `to_waypoint_id` VARCHAR(100) NOT NULL,
    `is_bidirectional` BOOLEAN NOT NULL DEFAULT TRUE,
    `traversal_cost` DOUBLE NULL,
    `priority` INT NULL,
    `is_enabled` BOOLEAN NOT NULL DEFAULT TRUE,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    CONSTRAINT `pk_fms_edge` PRIMARY KEY (`edge_id`),
    CONSTRAINT `fk_fms_edge_map_profile`
        FOREIGN KEY (`map_id`)
        REFERENCES `map_profile` (`map_id`),
    CONSTRAINT `fk_fms_edge_from_waypoint`
        FOREIGN KEY (`from_waypoint_id`)
        REFERENCES `fms_waypoint` (`waypoint_id`),
    CONSTRAINT `fk_fms_edge_to_waypoint`
        FOREIGN KEY (`to_waypoint_id`)
        REFERENCES `fms_waypoint` (`waypoint_id`),
    KEY `idx_fms_edge_map_enabled`
        (`map_id`, `is_enabled`),
    KEY `idx_fms_edge_from_to`
        (`from_waypoint_id`, `to_waypoint_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""".strip(),
    )


def _create_fms_route_step() -> MigrationStep:
    return MigrationStep(
        "create_fms_route",
        """
CREATE TABLE IF NOT EXISTS `fms_route` (
    `route_id` VARCHAR(100) NOT NULL,
    `map_id` VARCHAR(100) NOT NULL,
    `route_name` VARCHAR(100) NOT NULL,
    `route_scope` VARCHAR(20) NOT NULL,
    `revision` INT UNSIGNED NOT NULL DEFAULT 1,
    `is_enabled` BOOLEAN NOT NULL DEFAULT TRUE,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    CONSTRAINT `pk_fms_route` PRIMARY KEY (`route_id`),
    CONSTRAINT `fk_fms_route_map_profile`
        FOREIGN KEY (`map_id`)
        REFERENCES `map_profile` (`map_id`),
    KEY `idx_fms_route_map_scope_enabled_name`
        (`map_id`, `route_scope`, `is_enabled`, `route_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""".strip(),
    )


def _create_fms_route_waypoint_step() -> MigrationStep:
    return MigrationStep(
        "create_fms_route_waypoint",
        """
CREATE TABLE IF NOT EXISTS `fms_route_waypoint` (
    `route_id` VARCHAR(100) NOT NULL,
    `sequence_no` INT UNSIGNED NOT NULL,
    `waypoint_id` VARCHAR(100) NOT NULL,
    `yaw_policy` VARCHAR(20) NOT NULL DEFAULT 'AUTO_NEXT',
    `fixed_pose_yaw` DOUBLE NULL,
    `stop_required` BOOLEAN NOT NULL DEFAULT TRUE,
    `dwell_sec` DOUBLE NULL,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    CONSTRAINT `pk_fms_route_waypoint` PRIMARY KEY (`route_id`, `sequence_no`),
    CONSTRAINT `fk_fms_route_waypoint_route`
        FOREIGN KEY (`route_id`)
        REFERENCES `fms_route` (`route_id`)
        ON DELETE CASCADE,
    CONSTRAINT `fk_fms_route_waypoint_waypoint`
        FOREIGN KEY (`waypoint_id`)
        REFERENCES `fms_waypoint` (`waypoint_id`),
    KEY `idx_fms_route_waypoint_waypoint` (`waypoint_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""".strip(),
    )


def _create_drive_task_detail_step() -> MigrationStep:
    return MigrationStep(
        "create_drive_task_detail",
        """
CREATE TABLE IF NOT EXISTS `drive_task_detail` (
    `task_id` BIGINT UNSIGNED NOT NULL,
    `route_id` VARCHAR(100) NOT NULL,
    `route_revision` INT UNSIGNED NOT NULL,
    `drive_status` VARCHAR(30) NOT NULL DEFAULT 'PENDING',
    `frame_id` VARCHAR(50) NOT NULL DEFAULT 'map',
    `waypoint_count` INT UNSIGNED NOT NULL DEFAULT 0,
    `current_waypoint_index` INT UNSIGNED NULL,
    `path_snapshot_json` JSON NOT NULL,
    `notes` TEXT NULL,
    CONSTRAINT `pk_drive_task_detail` PRIMARY KEY (`task_id`),
    CONSTRAINT `fk_drive_task_detail_task`
        FOREIGN KEY (`task_id`)
        REFERENCES `task` (`task_id`)
        ON DELETE CASCADE,
    CONSTRAINT `fk_drive_task_detail_route`
        FOREIGN KEY (`route_id`)
        REFERENCES `fms_route` (`route_id`),
    KEY `idx_drive_task_detail_route_revision` (`route_id`, `route_revision`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""".strip(),
    )


def _create_fms_reservation_step() -> MigrationStep:
    return MigrationStep(
        "create_fms_reservation",
        """
CREATE TABLE IF NOT EXISTS `fms_reservation` (
    `reservation_id` VARCHAR(100) NOT NULL,
    `task_id` BIGINT UNSIGNED NULL,
    `robot_id` VARCHAR(50) NOT NULL,
    `map_id` VARCHAR(100) NOT NULL,
    `resource_type` VARCHAR(20) NOT NULL,
    `resource_id` VARCHAR(100) NOT NULL,
    `waypoint_id` VARCHAR(100) NULL,
    `edge_id` VARCHAR(100) NULL,
    `reservation_status` VARCHAR(20) NOT NULL,
    `reserved_from` DATETIME(3) NULL,
    `reserved_until` DATETIME(3) NULL,
    `released_at` DATETIME(3) NULL,
    `reason_code` VARCHAR(100) NULL,
    `created_at` DATETIME(3) NOT NULL,
    `updated_at` DATETIME(3) NOT NULL,
    CONSTRAINT `pk_fms_reservation` PRIMARY KEY (`reservation_id`),
    CONSTRAINT `fk_fms_reservation_task`
        FOREIGN KEY (`task_id`)
        REFERENCES `task` (`task_id`)
        ON DELETE SET NULL,
    CONSTRAINT `fk_fms_reservation_robot`
        FOREIGN KEY (`robot_id`)
        REFERENCES `robot` (`robot_id`),
    CONSTRAINT `fk_fms_reservation_map_profile`
        FOREIGN KEY (`map_id`)
        REFERENCES `map_profile` (`map_id`),
    CONSTRAINT `fk_fms_reservation_waypoint`
        FOREIGN KEY (`waypoint_id`)
        REFERENCES `fms_waypoint` (`waypoint_id`),
    CONSTRAINT `fk_fms_reservation_edge`
        FOREIGN KEY (`edge_id`)
        REFERENCES `fms_edge` (`edge_id`),
    KEY `idx_fms_reservation_active_resource`
        (`map_id`, `resource_type`, `resource_id`, `reservation_status`,
         `reserved_until`),
    KEY `idx_fms_reservation_task_status`
        (`task_id`, `reservation_status`, `updated_at`),
    KEY `idx_fms_reservation_robot_status`
        (`robot_id`, `reservation_status`, `updated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""".strip(),
    )


def _record_migration_step() -> MigrationStep:
    return MigrationStep(
        "record_migration",
        """
INSERT INTO `ropi_schema_migration` (`migration_id`, `applied_at`)
VALUES (%s, NOW())
ON DUPLICATE KEY UPDATE `applied_at` = `applied_at`
""".strip(),
        (MIGRATION_ID,),
    )


class FmsDriveRuntimeSchemaMigration:
    def __init__(self, connection):
        self.connection = connection

    def inspect_schema(self) -> SchemaState:
        existing_tables = frozenset(self._list_tables())
        migration_already_applied = False

        if "ropi_schema_migration" in existing_tables:
            migration_already_applied = self._migration_applied()

        return SchemaState(
            existing_tables=existing_tables,
            migration_already_applied=migration_already_applied,
        )

    def build_steps(self, *, force=False) -> list[MigrationStep]:
        return build_fms_drive_runtime_schema_migration_steps(
            self.inspect_schema(),
            force=force,
        )

    def apply(self, *, force=False) -> list[MigrationStep]:
        steps = self.build_steps(force=force)
        if not steps:
            return []

        try:
            with self.connection.cursor() as cursor:
                for step in steps:
                    cursor.execute(step.sql, step.params)
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        return steps

    def _list_tables(self) -> list[str]:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
SELECT TABLE_NAME AS table_name
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE()
""".strip()
            )
            return [row["table_name"] for row in cursor.fetchall()]

    def _migration_applied(self) -> bool:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
SELECT 1 AS applied
FROM `ropi_schema_migration`
WHERE `migration_id` = %s
LIMIT 1
""".strip(),
                (MIGRATION_ID,),
            )
            return cursor.fetchone() is not None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Create missing FMS/DRIVE runtime schema tables."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the migration. Without this flag, only prints the planned steps.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run even when the migration history table says this migration was applied.",
    )
    args = parser.parse_args(argv)

    connection = get_connection()
    try:
        migration = FmsDriveRuntimeSchemaMigration(connection)
        if args.apply:
            steps = migration.apply(force=args.force)
            if not steps:
                print(f"{MIGRATION_ID}: already applied; no steps executed.")
                return 0
            print(f"{MIGRATION_ID}: applied {len(steps)} steps.")
            for step in steps:
                print(f"- {step.name}")
            return 0

        steps = migration.build_steps(force=args.force)
        if not steps:
            print(f"{MIGRATION_ID}: already applied; no steps planned.")
            return 0
        print(f"{MIGRATION_ID}: dry-run plan ({len(steps)} steps).")
        for index, step in enumerate(steps, start=1):
            print(f"\n-- {index}. {step.name}\n{step.preview()};")
        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
