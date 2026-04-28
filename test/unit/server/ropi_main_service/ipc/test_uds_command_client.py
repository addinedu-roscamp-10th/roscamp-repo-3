import asyncio
import os
import socket
import threading

import pytest

from server.ropi_main_service.ipc.uds_client import (
    RosServiceCommandError,
    UnixDomainSocketCommandClient,
)
from server.ropi_main_service.ipc.uds_protocol import decode_message_bytes, encode_message


def test_send_command_uses_unix_domain_socket_and_parses_response(tmp_path):
    socket_path = tmp_path / "ropi_ros_service.sock"
    received = {}
    ready = threading.Event()
    finished = threading.Event()

    def run_server():
        if socket_path.exists():
            socket_path.unlink()

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server_sock:
            server_sock.bind(str(socket_path))
            server_sock.listen(1)
            ready.set()

            conn, _ = server_sock.accept()
            with conn:
                data = conn.recv(4096)
                received["request"] = decode_message_bytes(data)
                conn.sendall(
                    encode_message(
                        {
                            "ok": True,
                            "payload": {
                                "accepted": True,
                                "goal_handle_id": "goal_handle_001",
                            },
                        }
                    )
                )
        finished.set()

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    ready.wait(timeout=2)

    client = UnixDomainSocketCommandClient(socket_path=str(socket_path), timeout=1.0)
    response = client.send_command(
        "navigate_to_goal",
        {
            "pinky_id": "pinky2",
            "goal": {"task_id": "task_delivery_001"},
        },
    )

    finished.wait(timeout=2)
    server_thread.join(timeout=2)

    assert received["request"] == {
        "command": "navigate_to_goal",
        "payload": {
            "pinky_id": "pinky2",
            "goal": {"task_id": "task_delivery_001"},
        },
    }
    assert response == {
        "accepted": True,
        "goal_handle_id": "goal_handle_001",
    }


def test_async_send_command_uses_unix_domain_socket_and_parses_response(tmp_path):
    socket_path = tmp_path / "ropi_ros_service.sock"
    received = {}

    async def handle_client(reader, writer):
        received["request"] = decode_message_bytes(await reader.readline())
        writer.write(
            encode_message(
                {
                    "ok": True,
                    "payload": {
                        "accepted": True,
                        "goal_handle_id": "goal_handle_001",
                    },
                }
            )
        )
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def scenario():
        server = await asyncio.start_unix_server(handle_client, path=str(socket_path))
        try:
            client = UnixDomainSocketCommandClient(socket_path=str(socket_path), timeout=1.0)
            return await client.async_send_command(
                "navigate_to_goal",
                {
                    "pinky_id": "pinky2",
                    "goal": {"task_id": "task_delivery_001"},
                },
            )
        finally:
            server.close()
            await server.wait_closed()

    response = asyncio.run(scenario())

    assert received["request"] == {
        "command": "navigate_to_goal",
        "payload": {
            "pinky_id": "pinky2",
            "goal": {"task_id": "task_delivery_001"},
        },
    }
    assert response == {
        "accepted": True,
        "goal_handle_id": "goal_handle_001",
    }


def test_send_command_raises_ros_service_command_error_when_socket_is_unavailable(tmp_path):
    socket_path = tmp_path / "missing.sock"
    client = UnixDomainSocketCommandClient(socket_path=str(socket_path), timeout=0.1)

    with pytest.raises(RosServiceCommandError, match="failed"):
        client.send_command(
            "navigate_to_goal",
            {
                "pinky_id": "pinky2",
                "goal": {"task_id": "task_delivery_001"},
            },
        )
