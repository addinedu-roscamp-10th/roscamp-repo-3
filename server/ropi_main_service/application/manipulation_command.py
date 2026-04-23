from server.ropi_main_service.ipc.uds_client import UnixDomainSocketCommandClient


FIXED_PHASE1_ROBOT_SLOT_ID = "robot_slot_a1"
ALLOWED_TRANSFER_DIRECTIONS = {
    "TO_ROBOT",
    "FROM_ROBOT",
}
DEFAULT_COMMAND_TIMEOUT_SEC = 30.0


class ManipulationCommandService:
    def __init__(self, command_client=None, command_timeout_sec=DEFAULT_COMMAND_TIMEOUT_SEC):
        self.command_client = command_client or UnixDomainSocketCommandClient()
        self.command_timeout_sec = float(command_timeout_sec)

    def execute(
        self,
        *,
        arm_id,
        task_id,
        transfer_direction,
        item_id,
        quantity,
        robot_slot_id=FIXED_PHASE1_ROBOT_SLOT_ID,
    ):
        self._validate_request(
            arm_id=arm_id,
            task_id=task_id,
            transfer_direction=transfer_direction,
            item_id=item_id,
            quantity=quantity,
            robot_slot_id=robot_slot_id,
        )

        goal = {
            "task_id": str(task_id).strip(),
            "transfer_direction": str(transfer_direction).strip(),
            "item_id": str(item_id).strip(),
            "quantity": int(quantity),
            "robot_slot_id": str(robot_slot_id).strip(),
        }

        return self.command_client.send_command(
            "execute_manipulation",
            {
                "arm_id": str(arm_id).strip(),
                "goal": goal,
            },
            timeout=self.command_timeout_sec,
        )

    @staticmethod
    def _validate_request(*, arm_id, task_id, transfer_direction, item_id, quantity, robot_slot_id):
        if not str(arm_id or "").strip():
            raise ValueError("arm_id가 필요합니다.")

        if not str(task_id or "").strip():
            raise ValueError("task_id가 필요합니다.")

        if str(transfer_direction or "").strip() not in ALLOWED_TRANSFER_DIRECTIONS:
            raise ValueError(f"transfer_direction이 범위를 벗어났습니다: {transfer_direction}")

        if not str(item_id or "").strip():
            raise ValueError("item_id가 필요합니다.")

        if int(quantity) <= 0:
            raise ValueError("quantity는 1 이상이어야 합니다.")

        if not str(robot_slot_id or "").strip():
            raise ValueError("robot_slot_id가 필요합니다.")
