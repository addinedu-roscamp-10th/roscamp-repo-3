import argparse

from server.ropi_main_service.application.fms_conflict_geometry import (
    build_geometry_conflict_zones,
)
from server.ropi_main_service.persistence.connection import get_connection


LIST_ENABLED_EDGE_GEOMETRY_SQL = """
SELECT
    edge.map_id,
    edge.edge_id,
    edge.from_waypoint_id,
    edge.to_waypoint_id,
    from_waypoint.pose_x AS from_x,
    from_waypoint.pose_y AS from_y,
    to_waypoint.pose_x AS to_x,
    to_waypoint.pose_y AS to_y
FROM fms_edge edge
JOIN fms_waypoint from_waypoint
    ON from_waypoint.waypoint_id = edge.from_waypoint_id
JOIN fms_waypoint to_waypoint
    ON to_waypoint.waypoint_id = edge.to_waypoint_id
WHERE edge.is_enabled = TRUE
  AND from_waypoint.is_enabled = TRUE
  AND to_waypoint.is_enabled = TRUE
  AND (%s IS NULL OR edge.map_id = %s)
ORDER BY edge.map_id ASC, edge.edge_id ASC
""".strip()

DISABLE_AUTO_ZONES_SQL = """
UPDATE fms_conflict_zone
SET is_enabled = FALSE,
    updated_at = NOW(3)
WHERE source_type = 'AUTO_GEOMETRY'
  AND (%s IS NULL OR map_id = %s)
""".strip()

DELETE_AUTO_ZONE_LINKS_SQL = """
DELETE edge_conflict_zone
FROM fms_edge_conflict_zone edge_conflict_zone
JOIN fms_conflict_zone conflict_zone
    ON conflict_zone.conflict_zone_id = edge_conflict_zone.conflict_zone_id
WHERE conflict_zone.source_type = 'AUTO_GEOMETRY'
  AND (%s IS NULL OR conflict_zone.map_id = %s)
""".strip()

UPSERT_CONFLICT_ZONE_SQL = """
INSERT INTO fms_conflict_zone (
    conflict_zone_id,
    map_id,
    zone_name,
    zone_type,
    source_type,
    center_x,
    center_y,
    radius_m,
    is_enabled,
    created_at,
    updated_at
) VALUES (
    %s, %s, %s, %s, %s, %s, %s, %s, TRUE, NOW(3), NOW(3)
)
ON DUPLICATE KEY UPDATE
    map_id = VALUES(map_id),
    zone_name = VALUES(zone_name),
    zone_type = VALUES(zone_type),
    source_type = VALUES(source_type),
    center_x = VALUES(center_x),
    center_y = VALUES(center_y),
    radius_m = VALUES(radius_m),
    is_enabled = TRUE,
    updated_at = NOW(3)
""".strip()

UPSERT_EDGE_CONFLICT_ZONE_SQL = """
INSERT INTO fms_edge_conflict_zone (
    edge_id,
    conflict_zone_id,
    map_id,
    created_at
) VALUES (
    %s, %s, %s, NOW(3)
)
ON DUPLICATE KEY UPDATE
    map_id = VALUES(map_id)
""".strip()


def sync_fms_conflict_zones(connection, *, map_id=None, radius_m=0.20, apply=False):
    normalized_map_id = str(map_id).strip() if map_id is not None else None
    if not normalized_map_id:
        normalized_map_id = None

    edge_rows = _list_edge_geometry(connection, map_id=normalized_map_id)
    result = build_geometry_conflict_zones(edge_rows, radius_m=radius_m)
    if not apply:
        return {
            "edge_count": len(edge_rows),
            "zone_count": len(result["zones"]),
            "link_count": len(result["edge_conflict_zones"]),
            "dry_run": True,
        }

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                DELETE_AUTO_ZONE_LINKS_SQL,
                (normalized_map_id, normalized_map_id),
            )
            cursor.execute(
                DISABLE_AUTO_ZONES_SQL,
                (normalized_map_id, normalized_map_id),
            )
            for zone in result["zones"]:
                cursor.execute(
                    UPSERT_CONFLICT_ZONE_SQL,
                    (
                        zone["conflict_zone_id"],
                        zone["map_id"],
                        zone["zone_name"],
                        zone["zone_type"],
                        zone["source_type"],
                        zone["center_x"],
                        zone["center_y"],
                        zone["radius_m"],
                    ),
                )
            for link in result["edge_conflict_zones"]:
                cursor.execute(
                    UPSERT_EDGE_CONFLICT_ZONE_SQL,
                    (
                        link["edge_id"],
                        link["conflict_zone_id"],
                        link["map_id"],
                    ),
                )
        connection.commit()
    except Exception:
        connection.rollback()
        raise

    return {
        "edge_count": len(edge_rows),
        "zone_count": len(result["zones"]),
        "link_count": len(result["edge_conflict_zones"]),
        "dry_run": False,
    }


def _list_edge_geometry(connection, *, map_id=None):
    with connection.cursor() as cursor:
        cursor.execute(LIST_ENABLED_EDGE_GEOMETRY_SQL, (map_id, map_id))
        return cursor.fetchall()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Derive FMS conflict-zone resources from enabled edge geometry."
    )
    parser.add_argument("--map-id", default=None, help="Optional FMS map ID filter.")
    parser.add_argument(
        "--radius-m",
        type=float,
        default=0.20,
        help="Radius stored for generated conflict zones.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply generated zones and edge mappings. Otherwise prints a dry run.",
    )
    args = parser.parse_args(argv)

    connection = get_connection()
    try:
        result = sync_fms_conflict_zones(
            connection,
            map_id=args.map_id,
            radius_m=args.radius_m,
            apply=args.apply,
        )
    finally:
        connection.close()

    mode = "applied" if args.apply else "dry-run"
    print(
        "fms_conflict_zone_geometry_sync: "
        f"{mode}; edges={result['edge_count']}, "
        f"zones={result['zone_count']}, links={result['link_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["sync_fms_conflict_zones"]
