from server.ropi_main_service.persistence.async_connection import (
    async_fetch_one,
    async_transaction,
)
from server.ropi_main_service.persistence.connection import fetch_one, get_connection
from server.ropi_main_service.persistence.repositories.delivery_task_cancel_policy import (
    DeliveryTaskCancelPolicy,
)
from server.ropi_main_service.persistence.sql_loader import load_sql


class DeliveryTaskCancelRepository:
    def __init__(self, *, policy=None):
        self.policy = policy or DeliveryTaskCancelPolicy()

    def get_delivery_task_cancel_target(self, task_id):
        numeric_task_id = self.policy.parse_task_id(task_id)
        if numeric_task_id is None:
            return self.policy.build_invalid_task_id_cancel_response()

        row = self._fetch_delivery_task_cancel_target(numeric_task_id)
        return self.policy.build_cancel_target_response(row, task_id=numeric_task_id)

    async def async_get_delivery_task_cancel_target(self, task_id):
        numeric_task_id = self.policy.parse_task_id(task_id)
        if numeric_task_id is None:
            return self.policy.build_invalid_task_id_cancel_response()

        row = await async_fetch_one(
            load_sql("delivery/find_delivery_task_for_cancel.sql"),
            (numeric_task_id,),
        )
        return self.policy.build_cancel_target_response(row, task_id=numeric_task_id)

    def record_delivery_task_cancel_result(self, *, task_id, cancel_response):
        numeric_task_id = self.policy.parse_task_id(task_id)
        if numeric_task_id is None:
            return self.policy.build_invalid_task_id_cancel_response()

        conn = get_connection()
        try:
            self._begin(conn)
            with conn.cursor() as cur:
                row = self._lock_delivery_task_cancel_target(cur, numeric_task_id)
                response = self._record_delivery_task_cancel_result(
                    cur,
                    row=row,
                    task_id=numeric_task_id,
                    cancel_response=cancel_response,
                )
                conn.commit()
                return response
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    async def async_record_delivery_task_cancel_result(self, *, task_id, cancel_response):
        numeric_task_id = self.policy.parse_task_id(task_id)
        if numeric_task_id is None:
            return self.policy.build_invalid_task_id_cancel_response()

        async with async_transaction() as cur:
            await cur.execute(
                load_sql("delivery/lock_delivery_task_for_cancel.sql"),
                (numeric_task_id,),
            )
            row = await cur.fetchone()
            return await self._async_record_delivery_task_cancel_result(
                cur,
                row=row,
                task_id=numeric_task_id,
                cancel_response=cancel_response,
            )

    def record_delivery_task_cancelled_result(self, *, task_id, workflow_response):
        numeric_task_id = self.policy.parse_task_id(task_id)
        if numeric_task_id is None:
            return self.policy.build_invalid_task_id_cancelled_response(workflow_response)

        conn = get_connection()
        try:
            self._begin(conn)
            with conn.cursor() as cur:
                row = self._lock_delivery_task_cancel_target(cur, numeric_task_id)
                response = self._record_delivery_task_cancelled_result(
                    cur,
                    row=row,
                    task_id=numeric_task_id,
                    workflow_response=workflow_response,
                )
                conn.commit()
                return response
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    async def async_record_delivery_task_cancelled_result(self, *, task_id, workflow_response):
        numeric_task_id = self.policy.parse_task_id(task_id)
        if numeric_task_id is None:
            return self.policy.build_invalid_task_id_cancelled_response(workflow_response)

        async with async_transaction() as cur:
            await cur.execute(
                load_sql("delivery/lock_delivery_task_for_cancel.sql"),
                (numeric_task_id,),
            )
            row = await cur.fetchone()
            return await self._async_record_delivery_task_cancelled_result(
                cur,
                row=row,
                task_id=numeric_task_id,
                workflow_response=workflow_response,
            )

    @staticmethod
    def _fetch_delivery_task_cancel_target(task_id):
        return fetch_one(
            load_sql("delivery/find_delivery_task_for_cancel.sql"),
            (task_id,),
        )

    @staticmethod
    def _lock_delivery_task_cancel_target(cur, task_id):
        cur.execute(
            load_sql("delivery/lock_delivery_task_for_cancel.sql"),
            (task_id,),
        )
        return cur.fetchone()

    def _record_delivery_task_cancel_result(self, cur, *, row, task_id, cancel_response):
        guard_response = self.policy.build_cancel_result_guard(row, task_id=task_id)
        if guard_response is not None:
            return guard_response

        return self._write_cancel_result(cur, row=row, cancel_response=cancel_response)

    async def _async_record_delivery_task_cancel_result(self, cur, *, row, task_id, cancel_response):
        guard_response = self.policy.build_cancel_result_guard(row, task_id=task_id)
        if guard_response is not None:
            return guard_response

        return await self._async_write_cancel_result(cur, row=row, cancel_response=cancel_response)

    def _record_delivery_task_cancelled_result(self, cur, *, row, task_id, workflow_response):
        guard_response = self.policy.build_cancelled_result_guard(
            row,
            task_id=task_id,
            workflow_response=workflow_response,
        )
        if guard_response is not None:
            return guard_response

        return self._write_cancelled_result(cur, row=row, workflow_response=workflow_response)

    async def _async_record_delivery_task_cancelled_result(self, cur, *, row, task_id, workflow_response):
        guard_response = self.policy.build_cancelled_result_guard(
            row,
            task_id=task_id,
            workflow_response=workflow_response,
        )
        if guard_response is not None:
            return guard_response

        return await self._async_write_cancelled_result(cur, row=row, workflow_response=workflow_response)

    def _write_cancel_result(self, cur, *, row, cancel_response):
        plan = self.policy.build_cancel_result_write_plan(row=row, cancel_response=cancel_response)
        if plan["cancel_requested"]:
            cur.execute(
                load_sql("delivery/update_task_cancel_requested.sql"),
                plan["update_params"],
            )
            cur.execute(
                load_sql("delivery/insert_cancel_task_history.sql"),
                plan["history_params"],
            )

        cur.execute(
            load_sql("delivery/insert_cancel_task_event.sql"),
            plan["event_params"],
        )
        return self.policy.build_cancel_task_response(
            result_code=plan["result_code"],
            result_message=plan["result_message"],
            reason_code=plan["reason_code"],
            task_id=row.get("task_id"),
            task_status=plan["task_status"],
            assigned_robot_id=row.get("assigned_robot_id"),
            cancel_requested=plan["cancel_requested"],
            ros_result=cancel_response,
        )

    def _write_cancelled_result(self, cur, *, row, workflow_response):
        plan = self.policy.build_cancelled_result_write_plan(row=row, workflow_response=workflow_response)
        cur.execute(
            load_sql("delivery/update_task_cancelled.sql"),
            plan["update_params"],
        )
        cur.execute(
            load_sql("delivery/insert_cancelled_task_history.sql"),
            plan["history_params"],
        )
        cur.execute(
            load_sql("delivery/insert_cancel_task_event.sql"),
            plan["event_params"],
        )
        return self.policy.build_cancelled_task_response(
            result_code=plan["result_code"],
            result_message=plan["result_message"],
            reason_code=plan["reason_code"],
            task_id=row.get("task_id"),
            task_status=plan["task_status"],
            assigned_robot_id=row.get("assigned_robot_id"),
            workflow_response=workflow_response,
        )

    async def _async_write_cancel_result(self, cur, *, row, cancel_response):
        plan = self.policy.build_cancel_result_write_plan(row=row, cancel_response=cancel_response)
        if plan["cancel_requested"]:
            await cur.execute(
                load_sql("delivery/update_task_cancel_requested.sql"),
                plan["update_params"],
            )
            await cur.execute(
                load_sql("delivery/insert_cancel_task_history.sql"),
                plan["history_params"],
            )

        await cur.execute(
            load_sql("delivery/insert_cancel_task_event.sql"),
            plan["event_params"],
        )
        return self.policy.build_cancel_task_response(
            result_code=plan["result_code"],
            result_message=plan["result_message"],
            reason_code=plan["reason_code"],
            task_id=row.get("task_id"),
            task_status=plan["task_status"],
            assigned_robot_id=row.get("assigned_robot_id"),
            cancel_requested=plan["cancel_requested"],
            ros_result=cancel_response,
        )

    async def _async_write_cancelled_result(self, cur, *, row, workflow_response):
        plan = self.policy.build_cancelled_result_write_plan(row=row, workflow_response=workflow_response)
        await cur.execute(
            load_sql("delivery/update_task_cancelled.sql"),
            plan["update_params"],
        )
        await cur.execute(
            load_sql("delivery/insert_cancelled_task_history.sql"),
            plan["history_params"],
        )
        await cur.execute(
            load_sql("delivery/insert_cancel_task_event.sql"),
            plan["event_params"],
        )
        return self.policy.build_cancelled_task_response(
            result_code=plan["result_code"],
            result_message=plan["result_message"],
            reason_code=plan["reason_code"],
            task_id=row.get("task_id"),
            task_status=plan["task_status"],
            assigned_robot_id=row.get("assigned_robot_id"),
            workflow_response=workflow_response,
        )

    @staticmethod
    def _begin(conn):
        if hasattr(conn, "begin"):
            conn.begin()


__all__ = ["DeliveryTaskCancelRepository"]
