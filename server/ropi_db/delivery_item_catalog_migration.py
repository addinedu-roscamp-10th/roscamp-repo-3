import argparse
from dataclasses import dataclass

from server.ropi_main_service.persistence.connection import get_connection


MIGRATION_ID = "20260508_delivery_item_catalog"
TRANSPORT_ITEM_CATALOG = (
    (1, "의료", "의료키트", 30),
    (2, "생활용품", "기저귀", 30),
    (3, "식품", "오렌지", 30),
)


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


def build_delivery_item_catalog_migration_steps(
    state: SchemaState,
    *,
    force=False,
) -> list[MigrationStep]:
    if state.migration_already_applied and not force:
        return []

    steps = [_create_migration_history_step()]
    if "item" in state.existing_tables:
        steps.append(_upsert_transport_item_catalog_step())
        steps.append(
            _delete_unreferenced_unsupported_items_step(
                has_delivery_task_item="delivery_task_item" in state.existing_tables
            )
        )
        steps.append(_reset_item_auto_increment_step())
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


def _upsert_transport_item_catalog_step() -> MigrationStep:
    params = tuple(value for row in TRANSPORT_ITEM_CATALOG for value in row)
    return MigrationStep(
        "upsert_transport_item_catalog",
        """
INSERT INTO `item`
(`item_id`, `item_type`, `item_name`, `quantity`, `created_at`, `updated_at`)
VALUES
(%s, %s, %s, %s, NOW(), NOW()),
(%s, %s, %s, %s, NOW(), NOW()),
(%s, %s, %s, %s, NOW(), NOW())
ON DUPLICATE KEY UPDATE
    `item_type` = VALUES(`item_type`),
    `item_name` = VALUES(`item_name`),
    `quantity` = VALUES(`quantity`),
    `updated_at` = NOW()
""".strip(),
        params,
    )


def _delete_unreferenced_unsupported_items_step(
    *,
    has_delivery_task_item: bool,
) -> MigrationStep:
    if has_delivery_task_item:
        return MigrationStep(
            "delete_unreferenced_unsupported_items",
            """
DELETE i
FROM `item` AS i
LEFT JOIN `delivery_task_item` AS dti
    ON dti.`item_id` = i.`item_id`
WHERE i.`item_id` NOT IN (1, 2, 3)
  AND dti.`item_id` IS NULL
""".strip(),
        )
    return MigrationStep(
        "delete_unreferenced_unsupported_items",
        """
DELETE FROM `item`
WHERE `item_id` NOT IN (1, 2, 3)
""".strip(),
    )


def _reset_item_auto_increment_step() -> MigrationStep:
    return MigrationStep(
        "reset_item_auto_increment",
        "ALTER TABLE `item` AUTO_INCREMENT = 4",
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


class DeliveryItemCatalogMigration:
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
        return build_delivery_item_catalog_migration_steps(
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
        description="Migrate delivery item rows to the transport-team catalog."
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
        migration = DeliveryItemCatalogMigration(connection)
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
    "TRANSPORT_ITEM_CATALOG",
    "DeliveryItemCatalogMigration",
    "MigrationStep",
    "SchemaState",
    "build_delivery_item_catalog_migration_steps",
]
