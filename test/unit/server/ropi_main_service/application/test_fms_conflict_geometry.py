from server.ropi_main_service.application.fms_conflict_geometry import (
    build_geometry_conflict_zones,
)


def test_build_geometry_conflict_zones_maps_crossing_edges_to_shared_zone():
    result = build_geometry_conflict_zones(
        [
            {
                "map_id": "map_0504",
                "edge_id": "edge_route_1_cross",
                "from_waypoint_id": "a",
                "to_waypoint_id": "b",
                "from_x": 0.0,
                "from_y": 0.0,
                "to_x": 1.0,
                "to_y": 1.0,
            },
            {
                "map_id": "map_0504",
                "edge_id": "edge_route_2_cross",
                "from_waypoint_id": "c",
                "to_waypoint_id": "d",
                "from_x": 0.0,
                "from_y": 1.0,
                "to_x": 1.0,
                "to_y": 0.0,
            },
        ],
        radius_m=0.25,
    )

    assert len(result["zones"]) == 1
    zone = result["zones"][0]
    assert zone["conflict_zone_id"].startswith("cz_geo_")
    assert zone["map_id"] == "map_0504"
    assert zone["zone_type"] == "EDGE_INTERSECTION"
    assert zone["source_type"] == "AUTO_GEOMETRY"
    assert zone["center_x"] == 0.5
    assert zone["center_y"] == 0.5
    assert zone["radius_m"] == 0.25
    assert {
        link["edge_id"] for link in result["edge_conflict_zones"]
    } == {"edge_route_1_cross", "edge_route_2_cross"}
    assert {
        link["conflict_zone_id"] for link in result["edge_conflict_zones"]
    } == {zone["conflict_zone_id"]}


def test_build_geometry_conflict_zones_ignores_shared_waypoint_touch():
    result = build_geometry_conflict_zones(
        [
            {
                "map_id": "map_0504",
                "edge_id": "edge_ab",
                "from_waypoint_id": "a",
                "to_waypoint_id": "b",
                "from_x": 0.0,
                "from_y": 0.0,
                "to_x": 1.0,
                "to_y": 0.0,
            },
            {
                "map_id": "map_0504",
                "edge_id": "edge_bc",
                "from_waypoint_id": "b",
                "to_waypoint_id": "c",
                "from_x": 1.0,
                "from_y": 0.0,
                "to_x": 1.0,
                "to_y": 1.0,
            },
        ]
    )

    assert result == {"zones": [], "edge_conflict_zones": []}
