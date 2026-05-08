from server.ropi_db.delivery_item_catalog_migration import (
    MIGRATION_ID,
    TRANSPORT_ITEM_CATALOG,
    SchemaState,
    build_delivery_item_catalog_migration_steps,
)


def test_delivery_item_catalog_migration_upserts_transport_item_ids():
    state = SchemaState(existing_tables=frozenset({"item", "delivery_task_item"}))

    steps = build_delivery_item_catalog_migration_steps(state)
    by_name = {step.name: step for step in steps}

    assert by_name["upsert_transport_item_catalog"].params == (
        1,
        "의료",
        "의료키트",
        30,
        2,
        "생활용품",
        "기저귀",
        30,
        3,
        "식품",
        "오렌지",
        30,
    )
    assert TRANSPORT_ITEM_CATALOG == (
        (1, "의료", "의료키트", 30),
        (2, "생활용품", "기저귀", 30),
        (3, "식품", "오렌지", 30),
    )


def test_delivery_item_catalog_migration_removes_unreferenced_unsupported_items():
    state = SchemaState(existing_tables=frozenset({"item", "delivery_task_item"}))

    steps = build_delivery_item_catalog_migration_steps(state)
    delete_step = {step.name: step for step in steps}[
        "delete_unreferenced_unsupported_items"
    ]

    assert "NOT IN (1, 2, 3)" in delete_step.sql
    assert "LEFT JOIN `delivery_task_item`" in delete_step.sql
    assert "dti.`item_id` IS NULL" in delete_step.sql


def test_delivery_item_catalog_migration_resets_item_auto_increment():
    state = SchemaState(existing_tables=frozenset({"item"}))

    step_names = [
        step.name for step in build_delivery_item_catalog_migration_steps(state)
    ]

    assert "reset_item_auto_increment" in step_names


def test_delivery_item_catalog_migration_requires_item_table():
    state = SchemaState(existing_tables=frozenset())

    steps = build_delivery_item_catalog_migration_steps(state)

    assert [step.name for step in steps] == [
        "create_migration_history",
        "record_migration",
    ]


def test_delivery_item_catalog_migration_honors_applied_history_without_force():
    state = SchemaState(
        existing_tables=frozenset({"item", "delivery_task_item"}),
        migration_already_applied=True,
    )

    assert build_delivery_item_catalog_migration_steps(state) == []

    forced_steps = build_delivery_item_catalog_migration_steps(state, force=True)
    assert forced_steps[0].name == "create_migration_history"
    assert forced_steps[-1].params == (MIGRATION_ID,)
