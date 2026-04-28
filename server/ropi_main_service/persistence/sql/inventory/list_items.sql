SELECT
    CAST(item_id AS CHAR) AS item_id,
    item_name,
    quantity,
    item_type,
    created_at,
    updated_at
FROM item
ORDER BY item_name
