import argparse
from dataclasses import dataclass

from server.ropi_main_service.persistence.connection import get_connection

MIGRATION_ID = "20260508_guide_target_track_id_int"


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
    target_track_id_data_type: str | None = None
    migration_already_applied: bool = False


def build_guide_tracking_schema_migration_steps(
    state: SchemaState,
    *,
    force=False,
) -> list[MigrationStep]:
    if state.migration_already_applied and not force:
        return []

    steps = [_create_migration_history_step()]
    if (
        "guide_task_detail" in state.existing_tables
        and state.target_track_id_data_type != "int"
    ):
        steps.extend(
            [
                _normalize_legacy_target_track_id_step(),
                _alter_target_track_id_int_step(),
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


def _normalize_legacy_target_track_id_step() -> MigrationStep:
    return MigrationStep(
        "normalize_legacy_target_track_id",
        """
UPDATE `guide_task_detail`
SET `target_track_id` = NULL
WHERE `target_track_id` IS NOT NULL
  AND (
      TRIM(CAST(`target_track_id` AS CHAR)) = ''
      OR TRIM(CAST(`target_track_id` AS CHAR)) NOT REGEXP '^-?[0-9]+$'
  )
""".strip(),
    )


def _alter_target_track_id_int_step() -> MigrationStep:
    return MigrationStep(
        "alter_target_track_id_int",
        "ALTER TABLE `guide_task_detail` MODIFY `target_track_id` INT NULL",
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


class GuideTrackingSchemaMigration:
    def __init__(self, connection):
        self.connection = connection

    def inspect_schema(self) -> SchemaState:
        existing_tables = frozenset(self._list_tables())
        target_track_id_data_type = None
        migration_already_applied = False

        if "guide_task_detail" in existing_tables:
            target_track_id_data_type = self._column_data_type(
                "guide_task_detail",
                "target_track_id",
            )
        if "ropi_schema_migration" in existing_tables:
            migration_already_applied = self._migration_applied()

        return SchemaState(
            existing_tables=existing_tables,
            target_track_id_data_type=target_track_id_data_type,
            migration_already_applied=migration_already_applied,
        )

    def build_steps(self, *, force=False) -> list[MigrationStep]:
        return build_guide_tracking_schema_migration_steps(
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

    def _column_data_type(self, table_name: str, column_name: str) -> str | None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
SELECT DATA_TYPE AS data_type
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = %s
  AND COLUMN_NAME = %s
LIMIT 1
""".strip(),
                (table_name, column_name),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return str(row["data_type"] or "").strip().lower() or None

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
        description="Migrate guide tracking DB columns to the current contract."
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
        migration = GuideTrackingSchemaMigration(connection)
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
    "MIGRATION_ID",
    "GuideTrackingSchemaMigration",
    "MigrationStep",
    "SchemaState",
    "build_guide_tracking_schema_migration_steps",
]
