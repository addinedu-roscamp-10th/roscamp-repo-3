from server.ropi_main_service.application.delivery_config import get_delivery_runtime_config
from server.ropi_main_service.persistence.sql_loader import load_sql


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

    async def async_create_delivery_task_records(
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
        task_id = await self._async_insert_delivery_task(
            cur,
            request_id=request_id,
            idempotency_key=idempotency_key,
            caregiver_id=caregiver_id,
            priority=priority,
            destination_goal_pose_id=destination_goal_pose_id,
        )
        await self._async_insert_delivery_detail(
            cur,
            task_id=task_id,
            destination_goal_pose_id=destination_goal_pose_id,
            notes=notes,
        )
        await self._async_insert_delivery_item(
            cur,
            task_id=task_id,
            item_id=item_id,
            quantity=quantity,
        )
        await self._async_insert_initial_task_history(cur, task_id=task_id)
        await self._async_insert_initial_task_event(cur, task_id=task_id)
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
            load_sql("delivery/insert_delivery_task.sql"),
            (
                request_id,
                idempotency_key,
                str(caregiver_id),
                priority or "NORMAL",
                self.runtime_config.pinky_id,
                destination_goal_pose_id,
                self.runtime_config.map_id,
            ),
        )
        return cur.lastrowid

    async def _async_insert_delivery_task(
        self,
        cur,
        *,
        request_id,
        idempotency_key,
        caregiver_id,
        priority,
        destination_goal_pose_id,
    ):
        await cur.execute(
            load_sql("delivery/insert_delivery_task.sql"),
            (
                request_id,
                idempotency_key,
                str(caregiver_id),
                priority or "NORMAL",
                self.runtime_config.pinky_id,
                destination_goal_pose_id,
                self.runtime_config.map_id,
            ),
        )
        return cur.lastrowid

    def _insert_delivery_detail(self, cur, *, task_id, destination_goal_pose_id, notes):
        cur.execute(
            load_sql("delivery/insert_delivery_task_detail.sql"),
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

    async def _async_insert_delivery_detail(self, cur, *, task_id, destination_goal_pose_id, notes):
        await cur.execute(
            load_sql("delivery/insert_delivery_task_detail.sql"),
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
            load_sql("delivery/insert_delivery_task_item.sql"),
            (task_id, item_id, quantity),
        )

    @staticmethod
    async def _async_insert_delivery_item(cur, *, task_id, item_id, quantity):
        await cur.execute(
            load_sql("delivery/insert_delivery_task_item.sql"),
            (task_id, item_id, quantity),
        )

    @staticmethod
    def _insert_initial_task_history(cur, *, task_id):
        cur.execute(
            load_sql("delivery/insert_initial_task_history.sql"),
            (task_id, "delivery task accepted", "control_service"),
        )

    @staticmethod
    async def _async_insert_initial_task_history(cur, *, task_id):
        await cur.execute(
            load_sql("delivery/insert_initial_task_history.sql"),
            (task_id, "delivery task accepted", "control_service"),
        )

    @staticmethod
    def _insert_initial_task_event(cur, *, task_id):
        cur.execute(
            load_sql("delivery/insert_initial_task_event.sql"),
            (task_id, "delivery task accepted"),
        )

    @staticmethod
    async def _async_insert_initial_task_event(cur, *, task_id):
        await cur.execute(
            load_sql("delivery/insert_initial_task_event.sql"),
            (task_id, "delivery task accepted"),
        )


__all__ = ["DEFAULT_PICKUP_GOAL_POSE_ID", "DeliveryTaskRepository"]
