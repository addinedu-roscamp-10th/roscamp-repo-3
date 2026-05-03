import json
from datetime import date, datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[5]
APPLICATION_ROOT = REPO_ROOT / "server" / "ropi_main_service" / "application"


def _source(filename: str) -> str:
    return (APPLICATION_ROOT / filename).read_text(encoding="utf-8")


def test_application_formatting_primitives_are_shared_and_stable():
    from server.ropi_main_service.application.formatting import (
        bool_value,
        bounded_int,
        isoformat,
        json_object,
        normalize_optional_text,
        optional_float,
        optional_int,
    )

    assert json_object(b'{"value": 1}') == {"value": 1}
    assert json_object(json.dumps([1, 2])) == {}
    assert json_object("{bad") == {}
    assert bool_value("yes") is True
    assert bool_value("0") is False
    assert optional_int("12") == 12
    assert optional_int("bad") is None
    assert optional_float("1.5") == 1.5
    assert optional_float("") is None
    assert bounded_int("500", default=100, minimum=1, maximum=200) == 200
    assert bounded_int("bad", default=100, minimum=1, maximum=200) == 100
    assert normalize_optional_text("  room_301 ") == "room_301"
    assert normalize_optional_text("") is None
    assert isoformat(datetime(2026, 5, 3, 12, 0, 0)) == "2026-05-03T12:00:00"
    assert isoformat(date(2026, 5, 3)) == "2026-05-03"
    assert isoformat(None) is None
    assert isoformat(None, none_value="") == ""


def test_read_service_formatters_use_application_formatting_primitives():
    for filename in (
        "caregiver.py",
        "inventory.py",
        "coordinate_config_formatters.py",
    ):
        source = _source(filename)
        assert "server.ropi_main_service.application.formatting" in source

    caregiver_source = _source("caregiver.py")
    inventory_source = _source("inventory.py")
    coordinate_source = _source("coordinate_config_formatters.py")

    assert "def _isoformat" not in caregiver_source
    assert "def _json_object" not in caregiver_source
    assert "def _clean_filter" not in caregiver_source
    assert "def _to_int" not in inventory_source
    assert "def _isoformat" not in inventory_source
    assert "def json_object(" not in coordinate_source
    assert "def optional_int(" not in coordinate_source
    assert "def isoformat(" not in coordinate_source
