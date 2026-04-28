INSERT INTO delivery_task_item (
    task_id,
    item_id,
    requested_quantity,
    loaded_quantity,
    delivered_quantity,
    item_status,
    created_at,
    updated_at
)
VALUES (%s, %s, %s, 0, 0, 'REQUESTED', NOW(), NOW())
