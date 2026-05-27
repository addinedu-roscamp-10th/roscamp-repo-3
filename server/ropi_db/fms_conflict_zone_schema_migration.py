import argparse
from dataclasses import dataclass, field

from server.ropi_main_service.persistence.connection import get_connection


MIGRATION_ID = "20260527_fms_conflict_zone_schema"


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
    existing_columns: dict[str, frozenset[str]] = field(default_factory=dict)
    existing_constraints: frozenset[str] = frozenset()
    migration_already_applied: bool = False


def build_fms_conflict_zone_schema_migration_steps(
    state: SchemaState,
    *,
    force=False,
) -> list[MigrationStep]:
    if state.migration_already_applied and not force:
        return []

    steps = [_create_migration_history_step()]
    effective_tables = set(state.existing_tables)
    reservation_columns = set(state.existing_columns.get("fms_reservation") or [])
    effective_constraints = set(state.existing_constraints)

    if "map_profile" in effective_tables:
        if "fms_conflict_zone" not in effective_tables:
            steps.append(_create_fms_conflict_zone_step())
            effective_tables.add("fms_conflict_zone")

    if {"fms_edge", "fms_conflict_zone"}.issubset(effective_tables):
        if "fms_edge_conflict_zone" not in effective_tables:
            steps.append(_create_fms_edge_conflict_zone_step())
            effective_tables.add("fms_edge_conflict_zone")

    if "fms_reservation" in effective_tables:
        if "conflict_zone_id" not in reservation_columns:
            steps.append(_add_fms_reservation_conflict_zone_id_step())
            reservation_columns.add("conflict_zone_id")

        if (
            "fms_conflict_zone" in effective_tables
            and "conflict_zone_id" in reservation_columns
            and "fk_fms_reservation_conflict_zone" not in effective_constraints
        ):
            steps.append(_add_fms_reservation_conflict_zone_fk_step())
            effective_constraints.add("fk_fms_reservation_conflict_zone")

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


def _create_fms_conflict_zone_step() -> MigrationStep:
    return MigrationStep(
        "create_fms_conflict_zone",
        """
CREATE TABLE IF NOT EXISTS `fms_conflict_zone` (
    `conflict_zone_id` VARCHAR(100) NOT NULL,
    `map_id` VARCHAR(100) NOT NULL,
    `zone_name` VARCHAR(100) NOT NULL,
    `zone_type` VARCHAR(30) NOT NULL DEFAULT 'EDGE_INTERSECTION',
    `source_type` VARCHAR(30) NOT NULL DEFAULT 'AUTO_GEOMETRY',
    `center_x` DOUBLE NULL,
    `center_y` DOUBLE NULL,
    `radius_m` DOUBLE NULL,
    `is_enabled` BOOLEAN NOT NULL DEFAULT TRUE,
    `created_at` DATETIME(3) NOT NULL,
    `updated_at` DATETIME(3) NOT NULL,
    CONSTRAINT `pk_fms_conflict_zone` PRIMARY KEY (`conflict_zone_id`),
    CONSTRAINT `fk_fms_conflict_zone_map_profile`
        FOREIGN KEY (`map_id`)
        REFERENCES `map_profile` (`map_id`),
    KEY `idx_fms_conflict_zone_map_enabled_type`
        (`map_id`, `is_enabled`, `zone_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""".strip(),
    )


def _create_fms_edge_conflict_zone_step() -> MigrationStep:
    return MigrationStep(
        "create_fms_edge_conflict_zone",
        """
CREATE TABLE IF NOT EXISTS `fms_edge_conflict_zone` (
    `edge_id` VARCHAR(100) NOT NULL,
    `conflict_zone_id` VARCHAR(100) NOT NULL,
    `map_id` VARCHAR(100) NOT NULL,
    `created_at` DATETIME(3) NOT NULL,
    CONSTRAINT `pk_fms_edge_conflict_zone`
        PRIMARY KEY (`edge_id`, `conflict_zone_id`),
    CONSTRAINT `fk_fms_edge_conflict_zone_edge`
        FOREIGN KEY (`edge_id`)
        REFERENCES `fms_edge` (`edge_id`)
        ON DELETE CASCADE,
    CONSTRAINT `fk_fms_edge_conflict_zone_zone`
        FOREIGN KEY (`conflict_zone_id`)
        REFERENCES `fms_conflict_zone` (`conflict_zone_id`)
        ON DELETE CASCADE,
    KEY `idx_fms_edge_conflict_zone_zone` (`conflict_zone_id`),
    KEY `idx_fms_edge_conflict_zone_map` (`map_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""".strip(),
    )


def _add_fms_reservation_conflict_zone_id_step() -> MigrationStep:
    return MigrationStep(
        "add_fms_reservation_conflict_zone_id",
        """
ALTER TABLE `fms_reservation`
ADD COLUMN `conflict_zone_id` VARCHAR(100) NULL AFTER `edge_id`
""".strip(),
    )


def _add_fms_reservation_conflict_zone_fk_step() -> MigrationStep:
    return MigrationStep(
        "add_fms_reservation_conflict_zone_fk",
        """
ALTER TABLE `fms_reservation`
ADD CONSTRAINT `fk_fms_reservation_conflict_zone`
    FOREIGN KEY (`conflict_zone_id`)
    REFERENCES `fms_conflict_zone` (`conflict_zone_id`)
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


class FmsConflictZoneSchemaMigration:
    def __init__(self, connection):
        self.connection = connection

    def inspect_schema(self) -> SchemaState:
        existing_tables = frozenset(self._list_tables())
        migration_already_applied = False

        if "ropi_schema_migration" in existing_tables:
            migration_already_applied = self._migration_applied()

        return SchemaState(
            existing_tables=existing_tables,
            existing_columns={
                "fms_reservation": frozenset(self._list_columns("fms_reservation")),
            },
            existing_constraints=frozenset(self._list_constraints()),
            migration_already_applied=migration_already_applied,
        )

    def build_steps(self, *, force=False) -> list[MigrationStep]:
        return build_fms_conflict_zone_schema_migration_steps(
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

    def _list_columns(self, table_name: str) -> list[str]:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
SELECT COLUMN_NAME AS column_name
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = %s
""".strip(),
                (table_name,),
            )
            return [row["column_name"] for row in cursor.fetchall()]

    def _list_constraints(self) -> list[str]:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
SELECT CONSTRAINT_NAME AS constraint_name
FROM information_schema.TABLE_CONSTRAINTS
WHERE TABLE_SCHEMA = DATABASE()
""".strip()
            )
            return [row["constraint_name"] for row in cursor.fetchall()]

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
        description="Create missing FMS conflict-zone schema objects."
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
        migration = FmsConflictZoneSchemaMigration(connection)
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
