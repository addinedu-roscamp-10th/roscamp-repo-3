import argparse
import asyncio
import os
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

from server.ropi_main_service.application.auth import AuthService
from server.ropi_main_service.application.caregiver import CaregiverService
from server.ropi_main_service.application.goal_pose_navigation import GoalPoseNavigationService
from server.ropi_main_service.application.inventory import InventoryService
from server.ropi_main_service.application.patient import PatientService
from server.ropi_main_service.application.staff_call import StaffCallService
from server.ropi_main_service.application.task_request import DeliveryRequestService
from server.ropi_main_service.application.visit_guide import VisitGuideService
from server.ropi_main_service.application.visitor_info import VisitorInfoService
from server.ropi_main_service.application.visitor_register import VisitorRegisterService
from server.ropi_main_service.navigation import (
    FixedGoalPoseResolver,
    MappedGoalPoseResolver,
    get_delivery_navigation_config,
)
from server.ropi_main_service.transport.tcp_protocol import (
    MESSAGE_CODE_DELIVERY_CREATE_TASK,
    MESSAGE_CODE_HEARTBEAT,
    MESSAGE_CODE_INTERNAL_RPC,
    MESSAGE_CODE_LOGIN,
    TCPFrame,
    TCPFrameError,
    build_frame,
    encode_frame,
    read_frame_from_stream,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SERVER_ROOT = PROJECT_ROOT / "server"

load_dotenv(SERVER_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env")

CONTROL_SERVER_HOST = os.getenv("CONTROL_SERVER_HOST", "127.0.0.1")
CONTROL_SERVER_PORT = int(os.getenv("CONTROL_SERVER_PORT", "5050"))


def _serialize(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize(item) for item in value]
    return value


class CaregiverFacade:
    def __init__(self):
        self.service = CaregiverService()

    def get_dashboard_bundle(self):
        return {
            "summary": self.service.get_dashboard_summary(),
            "robots": self.service.get_robot_board_data(),
            "flow_data": self.service.get_flow_board_data(),
            "timeline_rows": self.service.get_timeline_data(),
        }


SERVICE_REGISTRY = {
    "caregiver": CaregiverFacade,
    "patient": PatientService,
    "inventory": InventoryService,
    "task_request": DeliveryRequestService,
    "visit_guide": VisitGuideService,
    "visitor_info": VisitorInfoService,
    "visitor_register": VisitorRegisterService,
    "staff_call": StaffCallService,
}


def build_delivery_request_service() -> DeliveryRequestService:
    navigation_config = get_delivery_navigation_config()
    pickup_goal_pose = navigation_config["pickup_goal_pose"]
    destination_goal_poses = navigation_config["destination_goal_poses"]

    goal_pose_navigation_service = None
    pickup_goal_pose_resolver = None
    destination_goal_pose_resolver = None

    if pickup_goal_pose is not None or destination_goal_poses:
        goal_pose_navigation_service = GoalPoseNavigationService()

    if pickup_goal_pose is not None:
        pickup_goal_pose_resolver = FixedGoalPoseResolver(pickup_goal_pose)

    if destination_goal_poses:
        destination_goal_pose_resolver = MappedGoalPoseResolver(destination_goal_poses)

    return DeliveryRequestService(
        goal_pose_navigation_service=goal_pose_navigation_service,
        pickup_goal_pose_resolver=pickup_goal_pose_resolver,
        destination_goal_pose_resolver=destination_goal_pose_resolver,
    )

class ControlServiceServer:
    def __init__(self, host: str = CONTROL_SERVER_HOST, port: int = CONTROL_SERVER_PORT):
        self.host = host
        self.port = port
        self._server = None

    def dispatch_frame(self, frame: TCPFrame) -> TCPFrame:
        payload = frame.payload or {}

        if frame.message_code == MESSAGE_CODE_HEARTBEAT:
            response_payload = {
                "message": "메인 서버 연결 정상",
                "server_time": datetime.now().isoformat(timespec="seconds"),
            }

            if payload.get("check_db"):
                try:
                    from server.ropi_main_service.persistence.connection import test_connection

                    db_ok, db_result = test_connection()
                    response_payload["db"] = {
                        "ok": db_ok,
                        "detail": db_result,
                    }
                except Exception as exc:
                    response_payload["db"] = {
                        "ok": False,
                        "detail": str(exc),
                    }

            return self._success_response(frame, response_payload)

        if frame.message_code == MESSAGE_CODE_LOGIN:
            ok, result = AuthService().authenticate(
                payload.get("login_id", ""),
                payload.get("password", ""),
                payload.get("role", ""),
            )
            if ok:
                return self._success_response(frame, result)
            return self._error_response(frame, "AUTH_FAILED", str(result))

        if frame.message_code == MESSAGE_CODE_DELIVERY_CREATE_TASK:
            return self._dispatch_delivery_create_task(frame, payload)

        if frame.message_code == MESSAGE_CODE_INTERNAL_RPC:
            return self._dispatch_rpc(frame, payload)

        return self._error_response(
            frame,
            "UNKNOWN_MESSAGE_CODE",
            f"지원하지 않는 message_code입니다: 0x{frame.message_code:04x}",
        )

    def _dispatch_delivery_create_task(self, frame: TCPFrame, payload: dict) -> TCPFrame:
        service = build_delivery_request_service()

        try:
            result = service.create_delivery_task(**payload)
        except Exception as exc:
            return self._error_response(frame, "DELIVERY_CREATE_ERROR", str(exc))

        return self._success_response(frame, result)

    def _dispatch_rpc(self, frame: TCPFrame, payload: dict):
        service_name = payload.get("service")
        method_name = payload.get("method")
        kwargs = payload.get("kwargs") or {}

        factory = SERVICE_REGISTRY.get(service_name)
        if factory is None:
            return self._error_response(
                frame,
                "UNKNOWN_SERVICE",
                f"지원하지 않는 서비스입니다: {service_name}",
            )

        service = factory()
        if not hasattr(service, method_name):
            return self._error_response(
                frame,
                "UNKNOWN_METHOD",
                f"지원하지 않는 메서드입니다: {service_name}.{method_name}",
            )

        try:
            result = getattr(service, method_name)(**kwargs)
        except Exception as exc:
            return self._error_response(frame, "RPC_ERROR", str(exc))

        return self._success_response(frame, result)

    async def start(self):
        self._server = await asyncio.start_server(
            self._handle_client,
            host=self.host,
            port=self.port,
        )

        sockets = self._server.sockets or []
        bound_host, bound_port = self.host, self.port
        if sockets:
            sockname = sockets[0].getsockname()
            bound_host, bound_port = sockname[0], sockname[1]

        print(
            f"ROPI Control Service listening on {bound_host}:{bound_port}",
            flush=True,
        )
        return self._server

    async def serve_forever(self):
        if self._server is None:
            await self.start()

        async with self._server:
            await self._server.serve_forever()

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ):
        try:
            while not reader.at_eof():
                try:
                    request_frame = await read_frame_from_stream(reader)
                except TCPFrameError:
                    break

                response_frame = self._build_response_frame(request_frame)
                writer.write(self._encode_response(response_frame))
                await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    def _build_response_frame(self, frame: TCPFrame):
        try:
            return self.dispatch_frame(frame)
        except Exception as exc:  # pragma: no cover
            return self._error_response(frame, "INTERNAL_ERROR", str(exc))

    @staticmethod
    def _encode_response(response: TCPFrame) -> bytes:
        serialized_payload = _serialize(response.payload)
        return encode_frame(
            TCPFrame(
                magic=response.magic,
                version=response.version,
                flags=response.flags,
                message_code=response.message_code,
                reserved=response.reserved,
                sequence_no=response.sequence_no,
                payload=serialized_payload,
            )
        )

    @staticmethod
    def _success_response(frame: TCPFrame, payload: dict) -> TCPFrame:
        return build_frame(
            frame.message_code,
            frame.sequence_no,
            payload,
            is_response=True,
        )

    @staticmethod
    def _error_response(frame: TCPFrame, error_code: str, error: str) -> TCPFrame:
        return build_frame(
            frame.message_code,
            frame.sequence_no,
            {
                "error_code": error_code,
                "error": error,
            },
            is_response=True,
            is_error=True,
        )


def parse_args():
    parser = argparse.ArgumentParser(description="ROPI Main Control Service TCP server")
    parser.add_argument("--host", default=CONTROL_SERVER_HOST)
    parser.add_argument("--port", type=int, default=CONTROL_SERVER_PORT)
    return parser.parse_args()


async def _run_server(host: str, port: int):
    server = ControlServiceServer(host, port)
    await server.serve_forever()


def main():
    args = parse_args()
    try:
        asyncio.run(_run_server(args.host, args.port))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
