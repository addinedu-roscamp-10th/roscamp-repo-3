import base64
import hashlib

from server.ropi_main_service.application.coordinate_config_assets import (
    MapAssetReader,
)


def test_map_asset_reader_normalizes_default_encoding_by_asset_type():
    reader = MapAssetReader(max_bytes=1024)

    assert reader.normalize_request(asset_type="yaml", encoding=None) == (
        {"asset_type": "YAML", "encoding": "TEXT"},
        None,
    )
    assert reader.normalize_request(asset_type="pgm", encoding=None) == (
        {"asset_type": "PGM", "encoding": "BASE64"},
        None,
    )


def test_map_asset_reader_reads_yaml_text_from_map_profile_path(tmp_path):
    yaml_path = tmp_path / "map.yaml"
    yaml_text = "image: map.pgm\nresolution: 0.020\n"
    yaml_path.write_text(yaml_text, encoding="utf-8")

    response = MapAssetReader(max_bytes=1024).read(
        {"map_id": "map_test11_0423", "yaml_path": str(yaml_path)},
        asset_type="YAML",
        encoding="TEXT",
    )

    content_bytes = yaml_text.encode("utf-8")
    assert response["result_code"] == "OK"
    assert response["map_id"] == "map_test11_0423"
    assert response["content_text"] == yaml_text
    assert response["content_base64"] is None
    assert response["size_bytes"] == len(content_bytes)
    assert response["sha256"] == hashlib.sha256(content_bytes).hexdigest()


def test_map_asset_reader_reads_pgm_base64_from_map_profile_path(tmp_path):
    pgm_path = tmp_path / "map.pgm"
    pgm_bytes = b"P5\n2 1\n255\n\x00\xff"
    pgm_path.write_bytes(pgm_bytes)

    response = MapAssetReader(max_bytes=1024).read(
        {"map_id": "map_test11_0423", "pgm_path": str(pgm_path)},
        asset_type="PGM",
        encoding="BASE64",
    )

    assert response["result_code"] == "OK"
    assert response["content_text"] is None
    assert response["content_base64"] == base64.b64encode(pgm_bytes).decode("ascii")
    assert response["size_bytes"] == len(pgm_bytes)
    assert response["sha256"] == hashlib.sha256(pgm_bytes).hexdigest()
