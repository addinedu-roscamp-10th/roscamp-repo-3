from threading import Lock


class GuideTrackingSnapshotStore:
    def __init__(self):
        self._lock = Lock()
        self._by_task_id = {}
        self._by_pinky_id = {}

    def record(self, snapshot):
        normalized = self._normalize_snapshot(snapshot)
        task_id = normalized.get("task_id")
        pinky_id = normalized.get("pinky_id")

        with self._lock:
            current = self._by_task_id.get(task_id) if task_id is not None else None
            if current is not None and self._sequence(current) > self._sequence(normalized):
                return dict(current)

            if task_id is not None:
                self._by_task_id[task_id] = normalized
            if pinky_id is not None:
                self._by_pinky_id[pinky_id] = normalized
            return dict(normalized)

    def get(self, *, task_id=None, pinky_id=None):
        normalized_task_id = self._normalize_task_id(task_id)
        normalized_pinky_id = self._normalize_text(pinky_id)

        with self._lock:
            if normalized_task_id is not None:
                snapshot = self._by_task_id.get(normalized_task_id)
                if snapshot is not None:
                    return dict(snapshot)
                return None

            if normalized_pinky_id is not None:
                snapshot = self._by_pinky_id.get(normalized_pinky_id)
                if snapshot is not None:
                    return dict(snapshot)

        return None

    @classmethod
    def _normalize_snapshot(cls, snapshot):
        data = dict(snapshot or {})
        data["task_id"] = cls._normalize_task_id(data.get("task_id"))
        data["pinky_id"] = cls._normalize_text(data.get("pinky_id"))
        data["tracking_result_seq"] = cls._normalize_int(
            data.get("tracking_result_seq"),
            default=0,
        )
        return data

    @staticmethod
    def _sequence(snapshot):
        try:
            return int((snapshot or {}).get("tracking_result_seq") or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _normalize_task_id(value):
        raw = str(value or "").strip()
        if not raw:
            return None
        if raw.isdigit():
            return int(raw)
        return raw

    @staticmethod
    def _normalize_text(value):
        normalized = str(value or "").strip()
        return normalized or None

    @staticmethod
    def _normalize_int(value, *, default):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default


_default_store = GuideTrackingSnapshotStore()


def get_default_guide_tracking_snapshot_store():
    return _default_store


__all__ = [
    "GuideTrackingSnapshotStore",
    "get_default_guide_tracking_snapshot_store",
]
