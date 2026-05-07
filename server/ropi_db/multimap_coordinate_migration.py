import argparse
import re
from dataclasses import dataclass, field

from server.ropi_main_service.persistence.connection import get_connection


MIGRATION_ID = "20260507_multimap_coordinate_config"
OLD_MAP_ID = "map_test11_0423"
CONTROL_MAP_ID = "map_0504"
TRANSPORT_MAP_ID = "map_test12_0506"

_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_]+$")


@dataclass(frozen=True)
class ForeignKeyConstraint:
    name: str
    columns: tuple[str, ...]
    referenced_table: str
    referenced_columns: tuple[str, ...]


@dataclass(frozen=True)
class SchemaState:
    existing_tables: frozenset[str] = field(default_factory=frozenset)
    operation_zone_primary_key: tuple[str, ...] = ()
    goal_pose_operation_zone_foreign_keys: tuple[ForeignKeyConstraint, ...] = ()
    goal_pose_indexes: tuple[tuple[str, tuple[str, ...]], ...] = ()
    migration_already_applied: bool = False


@dataclass(frozen=True)
class MigrationStep:
    name: str
    sql: str
    params: tuple = ()

    def preview(self) -> str:
        if not self.params:
            return self.sql
        return f"{self.sql} -- params={self.params!r}"


def build_multimap_coordinate_migration_steps(
    state: SchemaState,
    *,
    force: bool = False,
) -> list[MigrationStep]:
    if state.migration_already_applied and not force:
        return []

    steps: list[MigrationStep] = [
        _create_migration_history_step(),
        _upsert_map_profiles_step(),
        *_old_map_reference_remap_steps(state.existing_tables),
        *_drop_outdated_goal_pose_operation_zone_fk_steps(
            state.goal_pose_operation_zone_foreign_keys
        ),
        *_operation_zone_primary_key_steps(state.operation_zone_primary_key),
        _seed_transport_operation_zones_step(),
        _seed_transport_goal_poses_step(),
        *_goal_pose_operation_zone_constraint_steps(
            state.goal_pose_operation_zone_foreign_keys,
            state.goal_pose_indexes,
        ),
        _delete_old_map_profile_step(),
        _record_migration_step(),
    ]
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


def _upsert_map_profiles_step() -> MigrationStep:
    return MigrationStep(
        "upsert_map_profiles",
        """
INSERT INTO `map_profile`
(`map_id`, `map_name`, `map_revision`, `git_ref`, `yaml_path`, `pgm_path`,
 `frame_id`, `is_active`, `created_at`, `updated_at`)
VALUES
(%s, %s, 1, NULL,
 'device/ropi_mobile/src/ropi_nav_config/maps/map_0504.yaml',
 'device/ropi_mobile/src/ropi_nav_config/maps/map_0504.pgm',
 'map', TRUE, NOW(), NOW()),
(%s, %s, 1, NULL,
 'device/ropi_mobile/src/ropi_nav_config/maps/map_test12_0506.yaml',
 'device/ropi_mobile/src/ropi_nav_config/maps/map_test12_0506.pgm',
 'map', FALSE, NOW(), NOW())
ON DUPLICATE KEY UPDATE
    `yaml_path` = VALUES(`yaml_path`),
    `pgm_path` = VALUES(`pgm_path`),
    `frame_id` = VALUES(`frame_id`),
    `is_active` = VALUES(`is_active`),
    `updated_at` = NOW()
""".strip(),
        (CONTROL_MAP_ID, CONTROL_MAP_ID, TRANSPORT_MAP_ID, TRANSPORT_MAP_ID),
    )


def _old_map_reference_remap_steps(
    existing_tables: frozenset[str],
) -> list[MigrationStep]:
    steps: list[MigrationStep] = []
    if "operation_zone" in existing_tables:
        steps.append(
            MigrationStep(
                "remap_old_operation_zones_to_control_map",
                """
UPDATE `operation_zone`
SET `map_id` = %s, `updated_at` = NOW()
WHERE `map_id` = %s
""".strip(),
                (CONTROL_MAP_ID, OLD_MAP_ID),
            )
        )
    if "patrol_area" in existing_tables:
        steps.append(
            MigrationStep(
                "remap_old_patrol_areas_to_control_map",
                """
UPDATE `patrol_area`
SET `map_id` = %s, `updated_at` = NOW()
WHERE `map_id` = %s
""".strip(),
                (CONTROL_MAP_ID, OLD_MAP_ID),
            )
        )
    if "goal_pose" in existing_tables:
        steps.extend(
            [
                MigrationStep(
                    "remap_old_transport_goal_poses_to_transport_map",
                    """
UPDATE `goal_pose`
SET `map_id` = %s, `updated_at` = NOW()
WHERE `map_id` = %s
  AND `goal_pose_id` IN
      ('pickup_supply', 'delivery_room_301', 'delivery_room_302',
       'delivery_room_305', 'dock_home')
""".strip(),
                    (TRANSPORT_MAP_ID, OLD_MAP_ID),
                ),
                MigrationStep(
                    "remap_old_guide_goal_poses_to_control_map",
                    """
UPDATE `goal_pose`
SET `map_id` = %s, `updated_at` = NOW()
WHERE `map_id` = %s
  AND `goal_pose_id` LIKE 'guide_room_%%'
""".strip(),
                    (CONTROL_MAP_ID, OLD_MAP_ID),
                ),
            ]
        )
    if "task" in existing_tables:
        steps.append(
            MigrationStep(
                "remap_old_task_maps",
                """
UPDATE `task`
SET `map_id` = CASE
    WHEN `task_type` = 'DELIVERY' THEN %s
    ELSE %s
END,
`updated_at` = NOW(3)
WHERE `map_id` = %s
""".strip(),
                (TRANSPORT_MAP_ID, CONTROL_MAP_ID, OLD_MAP_ID),
            )
        )
    for table_name in ("fms_waypoint", "fms_edge", "fms_route"):
        if table_name in existing_tables:
            steps.append(
                MigrationStep(
                    f"remap_old_{table_name}_rows_to_control_map",
                    f"""
UPDATE `{table_name}`
SET `map_id` = %s, `updated_at` = NOW()
WHERE `map_id` = %s
""".strip(),
                    (CONTROL_MAP_ID, OLD_MAP_ID),
                )
            )
    return steps


def _drop_outdated_goal_pose_operation_zone_fk_steps(
    foreign_keys: tuple[ForeignKeyConstraint, ...],
) -> list[MigrationStep]:
    steps = []
    for foreign_key in foreign_keys:
        if _is_goal_pose_composite_operation_zone_fk(foreign_key):
            continue
        steps.append(
            MigrationStep(
                f"drop_outdated_goal_pose_fk_{foreign_key.name}",
                (
                    "ALTER TABLE `goal_pose` "
                    f"DROP FOREIGN KEY {_quote_identifier(foreign_key.name)}"
                ),
            )
        )
    return steps


def _operation_zone_primary_key_steps(
    primary_key_columns: tuple[str, ...],
) -> list[MigrationStep]:
    if primary_key_columns == ("map_id", "zone_id"):
        return []
    steps = []
    if primary_key_columns:
        steps.append(
            MigrationStep(
                "drop_operation_zone_primary_key",
                "ALTER TABLE `operation_zone` DROP PRIMARY KEY",
            )
        )
    steps.append(
        MigrationStep(
            "add_operation_zone_composite_primary_key",
            (
                "ALTER TABLE `operation_zone` "
                "ADD CONSTRAINT `pk_operation_zone` PRIMARY KEY (`map_id`, `zone_id`)"
            ),
        )
    )
    return steps


def _seed_transport_operation_zones_step() -> MigrationStep:
    return MigrationStep(
        "seed_transport_operation_zones",
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
 TRUE, NOW(), NOW()),
('supply_station', %s, '물품 적재 위치', 'SUPPLY_STATION', 1,
 '{"type":"POLYGON","header":{"frame_id":"map"},"vertices":[{"x":-0.3,"y":-0.9},{"x":0.6,"y":-0.9},{"x":0.6,"y":-0.1},{"x":-0.3,"y":-0.1}]}',
 TRUE, NOW(), NOW()),
('dock', %s, '충전소', 'DOCK', 1,
 '{"type":"POLYGON","header":{"frame_id":"map"},"vertices":[{"x":0.5,"y":-0.1},{"x":1.2,"y":-0.1},{"x":1.2,"y":0.6},{"x":0.5,"y":0.6}]}',
 TRUE, NOW(), NOW())
ON DUPLICATE KEY UPDATE
    `zone_id` = `zone_id`
""".strip(),
        (
            TRANSPORT_MAP_ID,
            TRANSPORT_MAP_ID,
            TRANSPORT_MAP_ID,
            TRANSPORT_MAP_ID,
            TRANSPORT_MAP_ID,
        ),
    )


def _seed_transport_goal_poses_step() -> MigrationStep:
    return MigrationStep(
        "seed_transport_goal_poses",
        """
INSERT INTO `goal_pose`
(`goal_pose_id`, `map_id`, `zone_id`, `purpose`, `pose_x`, `pose_y`, `pose_yaw`,
 `frame_id`, `is_enabled`, `created_at`, `updated_at`)
VALUES
('pickup_supply', %s, 'supply_station', 'PICKUP', 0.64, -0.44, 3.141592653589793,
 'map', TRUE, NOW(), NOW()),
('delivery_room_301', %s, 'room_301', 'DESTINATION', 1.6838363409042358,
 -0.4915957748889923, 1.5707963267948966, 'map', TRUE, NOW(), NOW()),
('delivery_room_302', %s, 'room_302', 'DESTINATION', 3.0, 1.0, 0.0,
 'map', TRUE, NOW(), NOW()),
('delivery_room_305', %s, 'room_305', 'DESTINATION', 1.0, 4.0, 0.0,
 'map', TRUE, NOW(), NOW()),
('dock_home', %s, 'dock', 'DOCK', -0.009538442827761173,
 -0.006931785028427839, 0.0, 'map', TRUE, NOW(), NOW())
ON DUPLICATE KEY UPDATE
    `map_id` = VALUES(`map_id`),
    `zone_id` = VALUES(`zone_id`),
    `purpose` = VALUES(`purpose`),
    `pose_x` = VALUES(`pose_x`),
    `pose_y` = VALUES(`pose_y`),
    `pose_yaw` = VALUES(`pose_yaw`),
    `frame_id` = VALUES(`frame_id`),
    `is_enabled` = VALUES(`is_enabled`),
    `updated_at` = NOW()
""".strip(),
        (
            TRANSPORT_MAP_ID,
            TRANSPORT_MAP_ID,
            TRANSPORT_MAP_ID,
            TRANSPORT_MAP_ID,
            TRANSPORT_MAP_ID,
        ),
    )


def _goal_pose_operation_zone_constraint_steps(
    foreign_keys: tuple[ForeignKeyConstraint, ...],
    indexes: tuple[tuple[str, tuple[str, ...]], ...],
) -> list[MigrationStep]:
    steps = []
    if not _has_index_with_column_prefix(indexes, ("map_id", "zone_id")):
        steps.append(
            MigrationStep(
                "add_goal_pose_map_zone_index",
                "ALTER TABLE `goal_pose` ADD KEY `idx_goal_pose_map_zone` (`map_id`, `zone_id`)",
            )
        )
    if not any(_is_goal_pose_composite_operation_zone_fk(fk) for fk in foreign_keys):
        steps.append(
            MigrationStep(
                "add_goal_pose_operation_zone_composite_fk",
                """
ALTER TABLE `goal_pose`
ADD CONSTRAINT `fk_goal_pose_operation_zone`
FOREIGN KEY (`map_id`, `zone_id`)
REFERENCES `operation_zone` (`map_id`, `zone_id`)
""".strip(),
            )
        )
    return steps


def _delete_old_map_profile_step() -> MigrationStep:
    return MigrationStep(
        "delete_retired_old_map_profile",
        "DELETE FROM `map_profile` WHERE `map_id` = %s",
        (OLD_MAP_ID,),
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


def _is_goal_pose_composite_operation_zone_fk(
    foreign_key: ForeignKeyConstraint,
) -> bool:
    return (
        foreign_key.referenced_table == "operation_zone"
        and foreign_key.columns == ("map_id", "zone_id")
        and foreign_key.referenced_columns == ("map_id", "zone_id")
    )


def _has_index_with_column_prefix(
    indexes: tuple[tuple[str, tuple[str, ...]], ...],
    columns: tuple[str, ...],
) -> bool:
    return any(
        index_columns[: len(columns)] == columns for _name, index_columns in indexes
    )


def _quote_identifier(value: str) -> str:
    value = str(value or "").strip()
    if not _IDENTIFIER_RE.fullmatch(value):
        raise ValueError(f"Unsafe SQL identifier: {value!r}")
    return f"`{value}`"


class MultimapCoordinateConfigMigration:
    def __init__(self, connection):
        self.connection = connection

    def inspect_schema(self) -> SchemaState:
        existing_tables = frozenset(self._list_tables())
        operation_zone_primary_key = ()
        goal_pose_operation_zone_foreign_keys = ()
        goal_pose_indexes = ()
        migration_already_applied = False

        if "operation_zone" in existing_tables:
            operation_zone_primary_key = self._primary_key_columns("operation_zone")
        if "goal_pose" in existing_tables:
            goal_pose_operation_zone_foreign_keys = self._foreign_keys(
                "goal_pose",
                referenced_table="operation_zone",
            )
            goal_pose_indexes = self._indexes("goal_pose")
        if "ropi_schema_migration" in existing_tables:
            migration_already_applied = self._migration_applied()

        return SchemaState(
            existing_tables=existing_tables,
            operation_zone_primary_key=operation_zone_primary_key,
            goal_pose_operation_zone_foreign_keys=goal_pose_operation_zone_foreign_keys,
            goal_pose_indexes=goal_pose_indexes,
            migration_already_applied=migration_already_applied,
        )

    def build_steps(self, *, force=False) -> list[MigrationStep]:
        return build_multimap_coordinate_migration_steps(
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

    def _primary_key_columns(self, table_name: str) -> tuple[str, ...]:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
SELECT COLUMN_NAME AS column_name
FROM information_schema.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = %s
  AND CONSTRAINT_NAME = 'PRIMARY'
ORDER BY ORDINAL_POSITION
""".strip(),
                (table_name,),
            )
            return tuple(row["column_name"] for row in cursor.fetchall())

    def _foreign_keys(
        self,
        table_name: str,
        *,
        referenced_table: str | None = None,
    ) -> tuple[ForeignKeyConstraint, ...]:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
SELECT
    CONSTRAINT_NAME AS constraint_name,
    COLUMN_NAME AS column_name,
    REFERENCED_TABLE_NAME AS referenced_table_name,
    REFERENCED_COLUMN_NAME AS referenced_column_name,
    ORDINAL_POSITION AS ordinal_position
FROM information_schema.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = %s
  AND REFERENCED_TABLE_NAME IS NOT NULL
  AND (%s IS NULL OR REFERENCED_TABLE_NAME = %s)
ORDER BY CONSTRAINT_NAME, ORDINAL_POSITION
""".strip(),
                (table_name, referenced_table, referenced_table),
            )
            rows = cursor.fetchall()

        grouped: dict[str, list[dict]] = {}
        for row in rows:
            grouped.setdefault(row["constraint_name"], []).append(row)

        constraints = []
        for constraint_name, constraint_rows in grouped.items():
            constraints.append(
                ForeignKeyConstraint(
                    name=constraint_name,
                    columns=tuple(row["column_name"] for row in constraint_rows),
                    referenced_table=constraint_rows[0]["referenced_table_name"],
                    referenced_columns=tuple(
                        row["referenced_column_name"] for row in constraint_rows
                    ),
                )
            )
        return tuple(constraints)

    def _indexes(self, table_name: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
SELECT
    INDEX_NAME AS index_name,
    COLUMN_NAME AS column_name,
    SEQ_IN_INDEX AS sequence_in_index
FROM information_schema.STATISTICS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = %s
ORDER BY INDEX_NAME, SEQ_IN_INDEX
""".strip(),
                (table_name,),
            )
            rows = cursor.fetchall()

        grouped: dict[str, list[dict]] = {}
        for row in rows:
            grouped.setdefault(row["index_name"], []).append(row)
        return tuple(
            (index_name, tuple(row["column_name"] for row in index_rows))
            for index_name, index_rows in grouped.items()
        )

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
        description="Migrate coordinate configuration DB data to the multi-map contract."
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
        migration = MultimapCoordinateConfigMigration(connection)
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
    "OLD_MAP_ID",
    "TRANSPORT_MAP_ID",
    "ForeignKeyConstraint",
    "MigrationStep",
    "MultimapCoordinateConfigMigration",
    "SchemaState",
    "build_multimap_coordinate_migration_steps",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
