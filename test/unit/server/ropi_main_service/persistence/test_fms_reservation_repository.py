from server.ropi_main_service.persistence.repositories.fms_reservation_repository import (
    FmsReservationRepository,
)


def test_fms_reservation_repository_normalizes_conflict_zone_resource():
    normalized = FmsReservationRepository._normalize_resource(
        {
            "resource_type": "CONFLICT_ZONE",
            "resource_id": "cz_geo_cross_01",
        }
    )

    assert normalized == {
        "key": ("CONFLICT_ZONE", "cz_geo_cross_01"),
        "resource_type": "CONFLICT_ZONE",
        "resource_id": "cz_geo_cross_01",
        "waypoint_id": None,
        "edge_id": None,
        "conflict_zone_id": "cz_geo_cross_01",
    }
