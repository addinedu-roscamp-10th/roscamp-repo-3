from hashlib import sha1
from itertools import combinations


EPSILON = 1.0e-9


def build_geometry_conflict_zones(edge_rows, *, radius_m=0.20):
    edges = [_normalize_edge(row) for row in edge_rows or []]
    edges = [edge for edge in edges if edge is not None]

    zones_by_id = {}
    links = set()
    for left, right in combinations(edges, 2):
        if left["map_id"] != right["map_id"]:
            continue
        if _share_waypoint(left, right):
            continue

        point = _segment_conflict_point(left, right)
        if point is None:
            continue

        zone_id = _conflict_zone_id(left["map_id"], left["edge_id"], right["edge_id"])
        zones_by_id[zone_id] = {
            "conflict_zone_id": zone_id,
            "map_id": left["map_id"],
            "zone_name": _zone_name(left["edge_id"], right["edge_id"]),
            "zone_type": "EDGE_INTERSECTION",
            "source_type": "AUTO_GEOMETRY",
            "center_x": _round_point(point[0]),
            "center_y": _round_point(point[1]),
            "radius_m": float(radius_m),
            "is_enabled": True,
        }
        links.add((left["edge_id"], zone_id, left["map_id"]))
        links.add((right["edge_id"], zone_id, right["map_id"]))

    return {
        "zones": [zones_by_id[zone_id] for zone_id in sorted(zones_by_id)],
        "edge_conflict_zones": [
            {
                "edge_id": edge_id,
                "conflict_zone_id": zone_id,
                "map_id": map_id,
            }
            for edge_id, zone_id, map_id in sorted(links)
        ],
    }


def _normalize_edge(row):
    row = row if isinstance(row, dict) else {}
    edge_id = str(row.get("edge_id") or "").strip()
    map_id = str(row.get("map_id") or "").strip()
    if not edge_id or not map_id:
        return None

    try:
        from_x = float(row.get("from_x"))
        from_y = float(row.get("from_y"))
        to_x = float(row.get("to_x"))
        to_y = float(row.get("to_y"))
    except (TypeError, ValueError):
        return None

    if _same_point((from_x, from_y), (to_x, to_y)):
        return None

    return {
        "edge_id": edge_id,
        "map_id": map_id,
        "from_waypoint_id": str(row.get("from_waypoint_id") or "").strip(),
        "to_waypoint_id": str(row.get("to_waypoint_id") or "").strip(),
        "from": (from_x, from_y),
        "to": (to_x, to_y),
    }


def _share_waypoint(left, right):
    left_waypoints = {left["from_waypoint_id"], left["to_waypoint_id"]} - {""}
    right_waypoints = {right["from_waypoint_id"], right["to_waypoint_id"]} - {""}
    return bool(left_waypoints & right_waypoints)


def _segment_conflict_point(left, right):
    p = left["from"]
    r = _sub(left["to"], p)
    q = right["from"]
    s = _sub(right["to"], q)
    denominator = _cross(r, s)
    qp = _sub(q, p)

    if abs(denominator) <= EPSILON:
        if abs(_cross(qp, r)) > EPSILON:
            return None
        return _collinear_overlap_midpoint(left["from"], left["to"], right["from"], right["to"])

    t = _cross(qp, s) / denominator
    u = _cross(qp, r) / denominator
    if -EPSILON <= t <= 1.0 + EPSILON and -EPSILON <= u <= 1.0 + EPSILON:
        return (p[0] + t * r[0], p[1] + t * r[1])
    return None


def _collinear_overlap_midpoint(a, b, c, d):
    use_x_axis = abs(b[0] - a[0]) >= abs(b[1] - a[1])
    axis = 0 if use_x_axis else 1

    left_start, left_end = sorted((a[axis], b[axis]))
    right_start, right_end = sorted((c[axis], d[axis]))
    overlap_start = max(left_start, right_start)
    overlap_end = min(left_end, right_end)
    if overlap_start > overlap_end + EPSILON:
        return None

    overlap_mid = (overlap_start + overlap_end) / 2.0
    total = b[axis] - a[axis]
    if abs(total) <= EPSILON:
        total = b[1 - axis] - a[1 - axis]
        if abs(total) <= EPSILON:
            return None
        t = ((a[1 - axis] + b[1 - axis]) / 2.0 - a[1 - axis]) / total
    else:
        t = (overlap_mid - a[axis]) / total
    return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))


def _conflict_zone_id(map_id, left_edge_id, right_edge_id):
    left, right = sorted((left_edge_id, right_edge_id))
    digest = sha1(f"{map_id}|{left}|{right}".encode("utf-8")).hexdigest()[:16]
    return f"cz_geo_{digest}"


def _zone_name(left_edge_id, right_edge_id):
    name = f"Geometry conflict {left_edge_id} x {right_edge_id}"
    return name[:100]


def _round_point(value):
    return round(float(value), 6)


def _sub(left, right):
    return (left[0] - right[0], left[1] - right[1])


def _cross(left, right):
    return left[0] * right[1] - left[1] * right[0]


def _same_point(left, right):
    return abs(left[0] - right[0]) <= EPSILON and abs(left[1] - right[1]) <= EPSILON


__all__ = ["build_geometry_conflict_zones"]
