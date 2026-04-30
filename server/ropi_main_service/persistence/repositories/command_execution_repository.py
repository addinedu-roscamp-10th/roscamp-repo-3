import json

from server.ropi_main_service.persistence.async_connection import (
    async_execute,
    async_transaction,
)
from server.ropi_main_service.persistence.connection import get_connection
from server.ropi_main_service.persistence.sql_loader import load_sql


class CommandExecutionRepository:
    def start_command_execution(
        self,
        *,
        task_id,
        transport,
        command_type,
        command_phase,
        target_component,
        target_robot_id,
        target_endpoint,
        request_payload,
    ):
        conn = get_connection()
        try:
            self._begin(conn)
            with conn.cursor() as cur:
                cur.execute(
                    load_sql("command_execution/insert_command_execution.sql"),
                    self._build_start_params(
                        task_id=task_id,
                        transport=transport,
                        command_type=command_type,
                        command_phase=command_phase,
                        target_component=target_component,
                        target_robot_id=target_robot_id,
                        target_endpoint=target_endpoint,
                        request_payload=request_payload,
                    ),
                )
                command_execution_id = cur.lastrowid
            conn.commit()
            return command_execution_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    async def async_start_command_execution(
        self,
        *,
        task_id,
        transport,
        command_type,
        command_phase,
        target_component,
        target_robot_id,
        target_endpoint,
        request_payload,
    ):
        async with async_transaction() as cur:
            await cur.execute(
                load_sql("command_execution/insert_command_execution.sql"),
                self._build_start_params(
                    task_id=task_id,
                    transport=transport,
                    command_type=command_type,
                    command_phase=command_phase,
                    target_component=target_component,
                    target_robot_id=target_robot_id,
                    target_endpoint=target_endpoint,
                    request_payload=request_payload,
                ),
            )
            return cur.lastrowid

    def finish_command_execution(
        self,
        *,
        command_execution_id,
        accepted,
        result_code,
        result_message,
        response_payload,
    ):
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    load_sql("command_execution/update_command_execution_result.sql"),
                    self._build_finish_params(
                        command_execution_id=command_execution_id,
                        accepted=accepted,
                        result_code=result_code,
                        result_message=result_message,
                        response_payload=response_payload,
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    async def async_finish_command_execution(
        self,
        *,
        command_execution_id,
        accepted,
        result_code,
        result_message,
        response_payload,
    ):
        await async_execute(
            load_sql("command_execution/update_command_execution_result.sql"),
            self._build_finish_params(
                command_execution_id=command_execution_id,
                accepted=accepted,
                result_code=result_code,
                result_message=result_message,
                response_payload=response_payload,
            ),
        )

    @classmethod
    def _build_start_params(
        cls,
        *,
        task_id,
        transport,
        command_type,
        command_phase,
        target_component,
        target_robot_id,
        target_endpoint,
        request_payload,
    ):
        return (
            cls._parse_optional_task_id(task_id),
            cls._normalize_text(transport),
            cls._normalize_text(command_type),
            cls._normalize_optional_text(command_phase),
            cls._normalize_text(target_component),
            cls._normalize_optional_text(target_robot_id),
            cls._normalize_optional_text(target_endpoint),
            cls._json_dumps(request_payload),
        )

    @classmethod
    def _build_finish_params(
        cls,
        *,
        command_execution_id,
        accepted,
        result_code,
        result_message,
        response_payload,
    ):
        return (
            accepted,
            cls._normalize_optional_text(result_code),
            cls._normalize_optional_text(result_message),
            cls._json_dumps(response_payload),
            int(command_execution_id),
        )

    @staticmethod
    def _parse_optional_task_id(value):
        raw = str(value or "").strip()
        if raw.isdigit():
            return int(raw)
        return None

    @staticmethod
    def _normalize_text(value):
        return str(value or "").strip()

    @classmethod
    def _normalize_optional_text(cls, value):
        normalized = cls._normalize_text(value)
        return normalized or None

    @staticmethod
    def _json_dumps(value):
        return json.dumps(value or {}, ensure_ascii=False)

    @staticmethod
    def _begin(conn):
        if hasattr(conn, "begin"):
            conn.begin()


__all__ = ["CommandExecutionRepository"]
