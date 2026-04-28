from server.ropi_main_service.application.delivery_config import get_delivery_runtime_config


DEFAULT_PICKUP_GOAL_POSE_ID = "pickup_supply"


class DeliveryTaskRepository:
    def __init__(self, runtime_config=None):
        self.runtime_config = runtime_config or get_delivery_runtime_config()

    def create_delivery_task_records(
        self,
        cur,
        *,
        request_id,
        idempotency_key,
        caregiver_id,
        priority,
        destination_goal_pose_id,
        notes,
        item_id,
        quantity,
    ):
        task_id = self._insert_delivery_task(
            cur,
            request_id=request_id,
            idempotency_key=idempotency_key,
            caregiver_id=caregiver_id,
            priority=priority,
            destination_goal_pose_id=destination_goal_pose_id,
        )
        self._insert_delivery_detail(
            cur,
            task_id=task_id,
            destination_goal_pose_id=destination_goal_pose_id,
            notes=notes,
        )
        self._insert_delivery_item(
            cur,
            task_id=task_id,
            item_id=item_id,
            quantity=quantity,
        )
        self._insert_initial_task_history(cur, task_id=task_id)
        self._insert_initial_task_event(cur, task_id=task_id)
        return task_id

    def _insert_delivery_task(
        self,
        cur,
        *,
        request_id,
        idempotency_key,
        caregiver_id,
        priority,
        destination_goal_pose_id,
    ):
        cur.execute(
            """
            INSERT INTO task (
                task_type,
                request_id,
                idempotency_key,
                requester_type,
                requester_id,
                priority,
                task_status,
                phase,
                assigned_robot_id,
                map_id,
                created_at,
                updated_at
            )
            SELECT
                'DELIVERY',
                %s,
                %s,
                'CAREGIVER',
                %s,
                %s,
                'WAITING_DISPATCH',
                'REQUESTED',
                %s,
                gp.map_id,
                NOW(3),
                NOW(3)
            FROM goal_pose gp
            WHERE gp.goal_pose_id = %s
            LIMIT 1
            """,
            (
                request_id,
                idempotency_key,
                str(caregiver_id),
                priority or "NORMAL",
                self.runtime_config.pinky_id,
                destination_goal_pose_id,
            ),
        )
        return cur.lastrowid

    def _insert_delivery_detail(self, cur, *, task_id, destination_goal_pose_id, notes):
        cur.execute(
            """
            INSERT INTO delivery_task_detail (
                task_id,
                pickup_goal_pose_id,
                destination_goal_pose_id,
                pickup_arm_robot_id,
                dropoff_arm_robot_id,
                robot_slot_id,
                notes
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                task_id,
                DEFAULT_PICKUP_GOAL_POSE_ID,
                destination_goal_pose_id,
                self.runtime_config.pickup_arm_robot_id,
                self.runtime_config.destination_arm_robot_id,
                self.runtime_config.robot_slot_id,
                notes,
            ),
        )

    @staticmethod
    def _insert_delivery_item(cur, *, task_id, item_id, quantity):
        cur.execute(
            """
            INSERT INTO delivery_task_item (
                task_id,
                item_id,
                requested_quantity,
                loaded_quantity,
                delivered_quantity,
                item_status,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, 0, 0, 'REQUESTED', NOW(), NOW())
            """,
            (task_id, item_id, quantity),
        )

    @staticmethod
    def _insert_initial_task_history(cur, *, task_id):
        cur.execute(
            """
            INSERT INTO task_state_history (
                task_id,
                from_status,
                to_status,
                from_phase,
                to_phase,
                reason_code,
                message,
                changed_by_component,
                changed_at
            )
            VALUES (
                %s,
                NULL,
                'WAITING_DISPATCH',
                NULL,
                'REQUESTED',
                NULL,
                %s,
                %s,
                NOW(3)
            )
            """,
            (task_id, "delivery task accepted", "control_service"),
        )

    @staticmethod
    def _insert_initial_task_event(cur, *, task_id):
        cur.execute(
            """
            INSERT INTO task_event_log (
                task_id,
                event_name,
                severity,
                component,
                result_code,
                message,
                occurred_at,
                created_at
            )
            VALUES (
                %s,
                'DELIVERY_TASK_ACCEPTED',
                'INFO',
                'control_service',
                'ACCEPTED',
                %s,
                NOW(3),
                NOW(3)
            )
            """,
            (task_id, "delivery task accepted"),
        )


__all__ = ["DEFAULT_PICKUP_GOAL_POSE_ID", "DeliveryTaskRepository"]
