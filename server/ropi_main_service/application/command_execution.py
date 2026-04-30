from dataclasses import dataclass

from server.ropi_main_service.persistence.repositories.command_execution_repository import (
    CommandExecutionRepository,
)


@dataclass(frozen=True)
class CommandExecutionSpec:
    task_id: str
    transport: str
    command_type: str
    command_phase: str | None
    target_component: str
    target_robot_id: str | None
    target_endpoint: str | None
    request_payload: dict


class CommandExecutionRecorder:
    def __init__(self, repository=None):
        self.repository = repository or CommandExecutionRepository()

    def record(self, spec: CommandExecutionSpec, command_runner):
        command_execution_id = self.repository.start_command_execution(**self._start_kwargs(spec))
        try:
            response = command_runner()
        except Exception as exc:
            self.repository.finish_command_execution(
                command_execution_id=command_execution_id,
                accepted=False,
                result_code="FAILED",
                result_message=str(exc),
                response_payload=self._build_exception_payload(exc),
            )
            raise

        self.repository.finish_command_execution(
            command_execution_id=command_execution_id,
            accepted=self._extract_accepted(response),
            result_code=self._extract_result_code(response),
            result_message=self._extract_result_message(response),
            response_payload=self._normalize_response_payload(response),
        )
        return response

    async def async_record(self, spec: CommandExecutionSpec, command_runner):
        command_execution_id = await self.repository.async_start_command_execution(**self._start_kwargs(spec))
        try:
            response = await command_runner()
        except Exception as exc:
            await self.repository.async_finish_command_execution(
                command_execution_id=command_execution_id,
                accepted=False,
                result_code="FAILED",
                result_message=str(exc),
                response_payload=self._build_exception_payload(exc),
            )
            raise

        await self.repository.async_finish_command_execution(
            command_execution_id=command_execution_id,
            accepted=self._extract_accepted(response),
            result_code=self._extract_result_code(response),
            result_message=self._extract_result_message(response),
            response_payload=self._normalize_response_payload(response),
        )
        return response

    @staticmethod
    def _start_kwargs(spec: CommandExecutionSpec):
        return {
            "task_id": spec.task_id,
            "transport": spec.transport,
            "command_type": spec.command_type,
            "command_phase": spec.command_phase,
            "target_component": spec.target_component,
            "target_robot_id": spec.target_robot_id,
            "target_endpoint": spec.target_endpoint,
            "request_payload": spec.request_payload,
        }

    @staticmethod
    def _extract_accepted(response):
        if not isinstance(response, dict):
            return None
        if "accepted" in response:
            return bool(response.get("accepted"))
        if "cancel_requested" in response:
            return bool(response.get("cancel_requested"))
        return None

    @staticmethod
    def _extract_result_code(response):
        if not isinstance(response, dict):
            return None
        result_code = str(response.get("result_code") or "").strip()
        return result_code or None

    @staticmethod
    def _extract_result_message(response):
        if not isinstance(response, dict):
            return None
        result_message = str(response.get("result_message") or "").strip()
        return result_message or None

    @staticmethod
    def _normalize_response_payload(response):
        if isinstance(response, dict):
            return response
        return {"response": response}

    @staticmethod
    def _build_exception_payload(exc: Exception):
        return {
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


__all__ = ["CommandExecutionRecorder", "CommandExecutionSpec"]
