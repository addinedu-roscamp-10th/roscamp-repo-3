import asyncio

from server.ropi_main_service.persistence.repositories import (
    coordinate_config_repository,
)


def test_coordinate_config_repository_fetches_active_map_and_child_rows(monkeypatch):
    calls = []

    def fake_fetch_one(query, params=None):
        calls.append(("one", query, params))
        return {"map_id": "map_test11_0423"}

    def fake_fetch_all(query, params=None):
        calls.append(("all", query, params))
        return [{"ok": True}]

    monkeypatch.setattr(coordinate_config_repository, "fetch_one", fake_fetch_one)
    monkeypatch.setattr(coordinate_config_repository, "fetch_all", fake_fetch_all)

    repository = coordinate_config_repository.CoordinateConfigRepository()

    assert repository.get_active_map_profile() == {"map_id": "map_test11_0423"}
    assert repository.get_operation_zones(
        map_id="map_test11_0423",
        include_disabled=False,
    ) == [{"ok": True}]
    assert repository.get_goal_poses(
        map_id="map_test11_0423",
        include_disabled=True,
    ) == [{"ok": True}]
    assert repository.get_patrol_areas(
        map_id="map_test11_0423",
        include_disabled=False,
    ) == [{"ok": True}]

    assert calls[0][0] == "one"
    assert "FROM map_profile" in calls[0][1]
    assert calls[0][2] is None
    assert calls[1][0] == "all"
    assert "FROM operation_zone" in calls[1][1]
    assert calls[1][2] == ("map_test11_0423", False)
    assert calls[2][0] == "all"
    assert "FROM goal_pose" in calls[2][1]
    assert "LEFT JOIN operation_zone" in calls[2][1]
    assert calls[2][2] == ("map_test11_0423", True)
    assert calls[3][0] == "all"
    assert "FROM patrol_area" in calls[3][1]
    assert "JSON_LENGTH(path_json, '$.poses')" in calls[3][1]
    assert calls[3][2] == ("map_test11_0423", False)


def test_coordinate_config_repository_exposes_async_fetch_methods(monkeypatch):
    calls = []

    async def fake_async_fetch_one(query, params=None):
        calls.append(("one", query, params))
        return {"map_id": "map_test11_0423"}

    async def fake_async_fetch_all(query, params=None):
        calls.append(("all", query, params))
        return [{"ok": True}]

    monkeypatch.setattr(
        coordinate_config_repository,
        "async_fetch_one",
        fake_async_fetch_one,
    )
    monkeypatch.setattr(
        coordinate_config_repository,
        "async_fetch_all",
        fake_async_fetch_all,
    )

    async def scenario():
        repository = coordinate_config_repository.CoordinateConfigRepository()
        active_map = await repository.async_get_active_map_profile()
        zones = await repository.async_get_operation_zones(
            map_id="map_test11_0423",
            include_disabled=False,
        )
        goals = await repository.async_get_goal_poses(
            map_id="map_test11_0423",
            include_disabled=False,
        )
        patrol_areas = await repository.async_get_patrol_areas(
            map_id="map_test11_0423",
            include_disabled=False,
        )
        return active_map, zones, goals, patrol_areas

    active_map, zones, goals, patrol_areas = asyncio.run(scenario())

    assert active_map == {"map_id": "map_test11_0423"}
    assert zones == [{"ok": True}]
    assert goals == [{"ok": True}]
    assert patrol_areas == [{"ok": True}]
    assert calls == [
        ("one", coordinate_config_repository.ACTIVE_MAP_PROFILE_SQL, None),
        (
            "all",
            coordinate_config_repository.LIST_OPERATION_ZONES_SQL,
            ("map_test11_0423", False),
        ),
        (
            "all",
            coordinate_config_repository.LIST_GOAL_POSES_SQL,
            ("map_test11_0423", False),
        ),
        (
            "all",
            coordinate_config_repository.LIST_PATROL_AREAS_SQL,
            ("map_test11_0423", False),
        ),
    ]
