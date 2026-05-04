import base64
import hashlib
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MAP_ASSET_MAX_BYTES = 1024 * 1024


class MapAssetReader:
    def __init__(self, *, max_bytes=None, project_root=None):
        self.project_root = Path(project_root or PROJECT_ROOT)
        self.max_bytes = (
            self._default_max_bytes()
            if max_bytes is None
            else max(1, int(max_bytes))
        )

    @classmethod
    def normalize_request(cls, *, asset_type, encoding):
        normalized_asset_type = cls._normalize_optional_text(asset_type)
        if normalized_asset_type:
            normalized_asset_type = normalized_asset_type.upper()

        if normalized_asset_type not in {"YAML", "PGM"}:
            return None, cls._error(
                result_code="INVALID_REQUEST",
                reason_code="MAP_ASSET_REQUEST_INVALID",
                result_message="asset_type이 유효하지 않습니다.",
                asset_type=normalized_asset_type,
                encoding=encoding,
            )

        normalized_encoding = cls._normalize_optional_text(encoding)
        if normalized_encoding:
            normalized_encoding = normalized_encoding.upper()
        if normalized_encoding is None:
            normalized_encoding = (
                "TEXT" if normalized_asset_type == "YAML" else "BASE64"
            )

        if (
            normalized_asset_type == "YAML"
            and normalized_encoding != "TEXT"
        ) or (
            normalized_asset_type == "PGM"
            and normalized_encoding != "BASE64"
        ):
            return None, cls._error(
                result_code="INVALID_REQUEST",
                reason_code="MAP_ASSET_REQUEST_INVALID",
                result_message="asset_type과 encoding 조합이 유효하지 않습니다.",
                asset_type=normalized_asset_type,
                encoding=normalized_encoding,
            )

        return {
            "asset_type": normalized_asset_type,
            "encoding": normalized_encoding,
        }, None

    def read(self, map_profile, *, asset_type, encoding):
        path_key = "yaml_path" if asset_type == "YAML" else "pgm_path"
        path = self._resolve_asset_path(map_profile.get(path_key))
        map_id = map_profile.get("map_id")

        if path is None or not path.is_file():
            return self._error(
                result_code="UNAVAILABLE",
                reason_code="MAP_ASSET_UNAVAILABLE",
                result_message="맵 asset 파일을 읽을 수 없습니다.",
                map_id=map_id,
                asset_type=asset_type,
                encoding=encoding,
            )

        try:
            size_bytes = path.stat().st_size
        except OSError:
            return self._error(
                result_code="UNAVAILABLE",
                reason_code="MAP_ASSET_UNAVAILABLE",
                result_message="맵 asset 파일 크기를 확인할 수 없습니다.",
                map_id=map_id,
                asset_type=asset_type,
                encoding=encoding,
            )

        if size_bytes > self.max_bytes:
            return self._error(
                result_code="PAYLOAD_TOO_LARGE",
                reason_code="MAP_ASSET_TOO_LARGE",
                result_message="맵 asset 응답 크기 제한을 초과했습니다.",
                map_id=map_id,
                asset_type=asset_type,
                encoding=encoding,
                size_bytes=size_bytes,
            )

        try:
            content_bytes = path.read_bytes()
        except OSError:
            return self._error(
                result_code="UNAVAILABLE",
                reason_code="MAP_ASSET_UNAVAILABLE",
                result_message="맵 asset 파일을 읽을 수 없습니다.",
                map_id=map_id,
                asset_type=asset_type,
                encoding=encoding,
            )

        if len(content_bytes) > self.max_bytes:
            return self._error(
                result_code="PAYLOAD_TOO_LARGE",
                reason_code="MAP_ASSET_TOO_LARGE",
                result_message="맵 asset 응답 크기 제한을 초과했습니다.",
                map_id=map_id,
                asset_type=asset_type,
                encoding=encoding,
                size_bytes=len(content_bytes),
            )

        try:
            content_text = (
                content_bytes.decode("utf-8") if encoding == "TEXT" else None
            )
        except UnicodeDecodeError:
            return self._error(
                result_code="UNAVAILABLE",
                reason_code="MAP_ASSET_UNAVAILABLE",
                result_message="맵 YAML asset을 UTF-8로 읽을 수 없습니다.",
                map_id=map_id,
                asset_type=asset_type,
                encoding=encoding,
            )

        content_base64 = (
            base64.b64encode(content_bytes).decode("ascii")
            if encoding == "BASE64"
            else None
        )
        return {
            "result_code": "OK",
            "result_message": None,
            "reason_code": None,
            "map_id": map_id,
            "asset_type": asset_type,
            "encoding": encoding,
            "content_text": content_text,
            "content_base64": content_base64,
            "size_bytes": len(content_bytes),
            "sha256": hashlib.sha256(content_bytes).hexdigest(),
        }

    def _resolve_asset_path(self, path_value):
        text = str(path_value or "").strip()
        if not text:
            return None
        path = Path(text)
        if not path.is_absolute():
            path = self.project_root / path
        return path.resolve()

    @staticmethod
    def _default_max_bytes():
        raw_value = os.getenv("ROPI_MAP_ASSET_MAX_BYTES")
        if raw_value in (None, ""):
            return DEFAULT_MAP_ASSET_MAX_BYTES
        try:
            return max(1, int(raw_value))
        except ValueError:
            return DEFAULT_MAP_ASSET_MAX_BYTES

    @staticmethod
    def _normalize_optional_text(value):
        text = str(value or "").strip()
        return text or None

    @staticmethod
    def _error(
        *,
        result_code,
        reason_code,
        result_message,
        map_id=None,
        asset_type=None,
        encoding=None,
        size_bytes=None,
    ):
        return {
            "result_code": result_code,
            "result_message": result_message,
            "reason_code": reason_code,
            "map_id": map_id,
            "asset_type": asset_type,
            "encoding": encoding,
            "content_text": None,
            "content_base64": None,
            "size_bytes": size_bytes,
            "sha256": None,
        }


__all__ = [
    "DEFAULT_MAP_ASSET_MAX_BYTES",
    "MapAssetReader",
    "PROJECT_ROOT",
]
