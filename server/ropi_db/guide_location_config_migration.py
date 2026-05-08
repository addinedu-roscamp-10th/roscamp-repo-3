import argparse
from dataclasses import dataclass

from server.ropi_main_service.persistence.connection import get_connection

MIGRATION_ID = "20260508_guide_location_config"
CONTROL_MAP_ID = "map_0504"


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


def build_guide_location_config_migration_steps(
    state: SchemaState,
    *,
    force=False,
) -> list[MigrationStep]:
    if state.migration_already_applied and not force:
        return []

    steps = [_create_migration_history_step()]
    if {"map_profile", "operation_zone", "goal_pose"}.issubset(state.existing_tables):
        steps.extend(
            [
                _ensure_control_map_profile_step(),
                _ensure_guide_operation_zones_step(),
                _seed_guide_goal_poses_step(),
            ]
        )
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


def _ensure_control_map_profile_step() -> MigrationStep:
    return MigrationStep(
        "ensure_control_map_profile",
        """
INSERT INTO `map_profile`
(`map_id`, `map_name`, `map_revision`, `git_ref`, `yaml_path`, `pgm_path`,
 `frame_id`, `is_active`, `created_at`, `updated_at`)
VALUES
(%s, %s, 1, NULL,
 'device/ropi_mobile/src/ropi_nav_config/maps/map_0504.yaml',
 'device/ropi_mobile/src/ropi_nav_config/maps/map_0504.pgm',
 'map', TRUE, NOW(), NOW())
ON DUPLICATE KEY UPDATE
    `yaml_path` = VALUES(`yaml_path`),
    `pgm_path` = VALUES(`pgm_path`),
    `frame_id` = VALUES(`frame_id`),
    `updated_at` = NOW()
""".strip(),
        (CONTROL_MAP_ID, CONTROL_MAP_ID),
    )


def _ensure_guide_operation_zones_step() -> MigrationStep:
    return MigrationStep(
        "ensure_guide_operation_zones",
        """
INSERT INTO `operation_zone`
(`zone_id`, `map_id`, `zone_name`, `zone_type`, `revision`, `boundary_json`,
 `is_enabled`, `created_at`, `updated_at`)
VALUES
('room_301', %s, '301호', 'ROOM', 1,
 '{"type":"POLYGON","header":{"frame_id":"map"},"vertices":[{"x":1.2,"y":-0.4},{"x":2.2,"y":-0.4},{"x":2.2,"y":0.5},{"x":1.2,"y":0.5}]}',
 TRUE, NOW(), NOW()),
('room_302', %s, '302호', 'ROOM', 1,
 '{"type":"POLYGON","header":{"frame_id":"map"},"vertices":[{"x":2.6,"y":0.6},{"x":3.4,"y":0.6},{"x":3.4,"y":1.4},{"x":2.6,"y":1.4}]}',
 TRUE, NOW(), NOW()),
('room_305', %s, '305호', 'ROOM', 1,
 '{"type":"POLYGON","header":{"frame_id":"map"},"vertices":[{"x":0.5,"y":3.5},{"x":1.5,"y":3.5},{"x":1.5,"y":4.5},{"x":0.5,"y":4.5}]}',
 TRUE, NOW(), NOW())
ON DUPLICATE KEY UPDATE
    `zone_id` = `zone_id`
""".strip(),
        (CONTROL_MAP_ID, CONTROL_MAP_ID, CONTROL_MAP_ID),
    )


def _seed_guide_goal_poses_step() -> MigrationStep:
    return MigrationStep(
        "seed_guide_goal_poses",
        """
INSERT INTO `goal_pose`
(`goal_pose_id`, `map_id`, `zone_id`, `purpose`, `pose_x`, `pose_y`, `pose_yaw`,
 `frame_id`, `is_enabled`, `created_at`, `updated_at`)
VALUES
('guide_room_301', %s, 'room_301', 'GUIDE_DESTINATION',
 1.6946025435218914, 0.0043433854992070454, 0.0,
 'map', TRUE, NOW(), NOW()),
('guide_room_302', %s, 'room_302', 'GUIDE_DESTINATION',
 3.0, 1.0, 0.0,
 'map', TRUE, NOW(), NOW()),
('guide_room_305', %s, 'room_305', 'GUIDE_DESTINATION',
 1.0, 4.0, 0.0,
 'map', TRUE, NOW(), NOW())
ON DUPLICATE KEY UPDATE
    `map_id` = VALUES(`map_id`),
    `zone_id` = VALUES(`zone_id`),
    `purpose` = VALUES(`purpose`),
    `frame_id` = VALUES(`frame_id`),
    `is_enabled` = VALUES(`is_enabled`),
    `updated_at` = NOW()
""".strip(),
        (CONTROL_MAP_ID, CONTROL_MAP_ID, CONTROL_MAP_ID),
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


class GuideLocationConfigMigration:
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
        return build_guide_location_config_migration_steps(
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
        description="Seed guide location config required by the phase-1 guide flow."
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
        migration = GuideLocationConfigMigration(connection)
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
        print("\nRun with --apply to execute this migration.")
        return 0
    finally:
        connection.close()


__all__ = [
    "CONTROL_MAP_ID",
    "MIGRATION_ID",
    "GuideLocationConfigMigration",
    "MigrationStep",
    "SchemaState",
    "build_guide_location_config_migration_steps",
]
