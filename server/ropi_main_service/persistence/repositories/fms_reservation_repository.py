from uuid import uuid4

from server.ropi_main_service.persistence.connection import get_connection
from server.ropi_main_service.persistence.sql_loader import load_sql


FIND_RESERVATION_SQL = load_sql("fms_reservation/find_reservation.sql")
FIND_ACTIVE_RESOURCE_RESERVATION_FOR_UPDATE_SQL = load_sql(
    "fms_reservation/find_active_resource_reservation_for_update.sql"
)
INSERT_RESERVATION_SQL = load_sql("fms_reservation/insert_reservation.sql")
LIST_ACTIVE_RESERVATIONS_SQL = load_sql(
    "fms_reservation/list_active_reservations.sql"
)
RELEASE_TASK_RESERVATIONS_SQL = load_sql(
    "fms_reservation/release_task_reservations.sql"
)
RELEASE_TASK_ROBOT_RESERVATIONS_SQL = load_sql(
    "fms_reservation/release_task_robot_reservations.sql"
)
RELEASE_TASK_RESOURCE_RESERVATIONS_SQL = load_sql(
    "fms_reservation/release_task_resource_reservations.sql"
)
RENEW_TASK_RESERVATIONS_SQL = load_sql(
    "fms_reservation/renew_task_reservations.sql"
)
RENEW_TASK_ROBOT_RESERVATIONS_SQL = load_sql(
    "fms_reservation/renew_task_robot_reservations.sql"
)


class FmsReservationRepository:
    def __init__(self, connection_factory=None, reservation_id_factory=None):
        self.connection_factory = connection_factory or get_connection
        self.reservation_id_factory = reservation_id_factory or self._new_reservation_id

    def get_reservation_snapshot(self, *, map_id=None):
        conn = self.connection_factory()
        try:
            with conn.cursor() as cur:
                cur.execute(LIST_ACTIVE_RESERVATIONS_SQL, self._map_filter_params(map_id))
                return cur.fetchall()
        finally:
            conn.close()

    def request_reservation(
        self,
        *,
        task_id,
        robot_id,
        map_id,
        resources,
        lease_sec,
    ):
        normalized_resources = [
            self._normalize_resource(resource) for resource in resources or []
        ]
        lease_sec = self._normalize_lease_sec(lease_sec)
        conn = self.connection_factory()
        try:
            conn.begin()
            with conn.cursor() as cur:
                held_rows = {}
                has_conflict = False
                for resource in normalized_resources:
                    cur.execute(
                        FIND_ACTIVE_RESOURCE_RESERVATION_FOR_UPDATE_SQL,
                        (
                            str(map_id),
                            resource["resource_type"],
                            resource["resource_id"],
                        ),
                    )
                    existing = cur.fetchone()
                    if existing is None:
                        continue
                    if self._same_task(existing.get("task_id"), task_id):
                        held_rows[resource["key"]] = existing
                        continue
                    has_conflict = True

                reservation_status = "WAITING" if has_conflict else "HELD"
                reason_code = (
                    "FMS_RESOURCE_ALREADY_HELD" if reservation_status == "WAITING" else None
                )
                reservations = []
                for resource in normalized_resources:
                    existing = held_rows.get(resource["key"])
                    if existing is not None:
                        reservations.append(existing)
                        continue

                    reservations.append(
                        self._insert_reservation(
                            cur,
                            task_id=task_id,
                            robot_id=robot_id,
                            map_id=map_id,
                            resource=resource,
                            reservation_status=reservation_status,
                            lease_sec=lease_sec,
                            reason_code=reason_code,
                        )
                    )

            conn.commit()
            return {
                "reservation_status": reservation_status,
                "reason_code": reason_code,
                "reservations": reservations,
            }
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def release_reservation(
        self,
        *,
        task_id,
        robot_id=None,
        reason_code=None,
        resources=None,
    ):
        normalized_resources = [
            self._normalize_resource(resource) for resource in resources or []
        ]
        conn = self.connection_factory()
        try:
            conn.begin()
            with conn.cursor() as cur:
                if normalized_resources:
                    released_count = 0
                    for resource in normalized_resources:
                        cur.execute(
                            RELEASE_TASK_RESOURCE_RESERVATIONS_SQL,
                            (
                                reason_code,
                                int(task_id),
                                str(robot_id),
                                resource["resource_type"],
                                resource["resource_id"],
                            ),
                        )
                        released_count += cur.rowcount
                elif robot_id:
                    cur.execute(
                        RELEASE_TASK_ROBOT_RESERVATIONS_SQL,
                        (reason_code, int(task_id), str(robot_id)),
                    )
                else:
                    cur.execute(
                        RELEASE_TASK_RESERVATIONS_SQL,
                        (reason_code, int(task_id)),
                    )
                    released_count = cur.rowcount
            conn.commit()
            return released_count
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def renew_reservation(self, *, task_id, robot_id=None, lease_sec=None):
        lease_sec = self._normalize_lease_sec(lease_sec)
        conn = self.connection_factory()
        try:
            conn.begin()
            with conn.cursor() as cur:
                if robot_id:
                    cur.execute(
                        RENEW_TASK_ROBOT_RESERVATIONS_SQL,
                        (lease_sec, int(task_id), str(robot_id)),
                    )
                else:
                    cur.execute(
                        RENEW_TASK_RESERVATIONS_SQL,
                        (lease_sec, int(task_id)),
                    )
                renewed_count = cur.rowcount
            conn.commit()
            return renewed_count
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _insert_reservation(
        self,
        cur,
        *,
        task_id,
        robot_id,
        map_id,
        resource,
        reservation_status,
        lease_sec,
        reason_code,
    ):
        reservation_id = self.reservation_id_factory()
        cur.execute(
            INSERT_RESERVATION_SQL,
            (
                reservation_id,
                int(task_id),
                str(robot_id),
                str(map_id),
                resource["resource_type"],
                resource["resource_id"],
                resource["waypoint_id"],
                resource["edge_id"],
                resource["conflict_zone_id"],
                reservation_status,
                reservation_status,
                reservation_status,
                lease_sec,
                reason_code,
            ),
        )
        cur.execute(FIND_RESERVATION_SQL, (reservation_id,))
        return cur.fetchone()

    @staticmethod
    def _normalize_resource(resource):
        resource_type = str(resource.get("resource_type") or "").strip().upper()
        resource_id = str(resource.get("resource_id") or "").strip()
        return {
            "key": (resource_type, resource_id),
            "resource_type": resource_type,
            "resource_id": resource_id,
            "waypoint_id": resource_id if resource_type == "WAYPOINT" else None,
            "edge_id": resource_id if resource_type == "EDGE" else None,
            "conflict_zone_id": (
                resource_id if resource_type == "CONFLICT_ZONE" else None
            ),
        }

    @staticmethod
    def _normalize_lease_sec(lease_sec):
        try:
            return max(1, int(lease_sec))
        except (TypeError, ValueError):
            return 30

    @staticmethod
    def _map_filter_params(map_id):
        normalized_map_id = str(map_id).strip() if map_id is not None else None
        if not normalized_map_id:
            normalized_map_id = None
        return (normalized_map_id, normalized_map_id)

    @staticmethod
    def _same_task(left, right):
        try:
            return int(left) == int(right)
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _new_reservation_id():
        return f"fms_resv_{uuid4().hex}"


__all__ = ["FmsReservationRepository"]
