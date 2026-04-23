from server.ropi_main_service.persistence.repositories.task_request_repository import DeliveryRequestRepository


class DeliveryRequestService:
    ACCEPTED = "ACCEPTED"
    INVALID_REQUEST = "INVALID_REQUEST"
    REJECTED = "REJECTED"
    DEFAULT_DELIVERY_NAVIGATION_TIMEOUT_SEC = 120

    def __init__(
        self,
        repository=None,
        goal_pose_navigation_service=None,
        destination_goal_pose_resolver=None,
        delivery_navigation_timeout_sec=DEFAULT_DELIVERY_NAVIGATION_TIMEOUT_SEC,
    ):
        self.repository = repository or DeliveryRequestRepository()
        self.goal_pose_navigation_service = goal_pose_navigation_service
        self.destination_goal_pose_resolver = destination_goal_pose_resolver
        self.delivery_navigation_timeout_sec = delivery_navigation_timeout_sec

    def get_product_names(self):
        products = self.repository.get_all_products()
        return [product["item_name"] for product in products]

    def get_delivery_items(self):
        return self.repository.get_all_products()

    def create_delivery_task(
        self,
        request_id,
        caregiver_id,
        item_id,
        quantity,
        destination_id,
        priority,
        notes=None,
        idempotency_key=None,
    ):
        invalid_response = self._validate_create_delivery_task_request(
            request_id=request_id,
            caregiver_id=caregiver_id,
            item_id=item_id,
            quantity=quantity,
            destination_id=destination_id,
            idempotency_key=idempotency_key,
        )
        if invalid_response is not None:
            return invalid_response

        response = self.repository.create_delivery_task(
            request_id=request_id,
            caregiver_id=caregiver_id,
            item_id=item_id,
            quantity=quantity,
            destination_id=destination_id,
            priority=priority,
            notes=notes,
            idempotency_key=idempotency_key,
        )
        self._wire_delivery_destination_navigation_if_needed(
            response=response,
            destination_id=destination_id,
        )
        return response

    def submit_delivery_request(
        self,
        item_name,
        quantity,
        destination,
        priority,
        detail,
        member_id,
    ):
        if not item_name or item_name == "등록된 물품 없음":
            return False, "물품 종류를 선택하세요."

        if quantity <= 0:
            return False, "수량은 1 이상이어야 합니다."

        if not destination:
            return False, "목적지를 선택하세요."

        if not member_id:
            return False, "로그인 사용자 정보가 없습니다."

        return self.repository.create_delivery_request(
            item_name=item_name,
            quantity=quantity,
            destination=destination,
            priority=priority,
            detail=detail,
            member_id=member_id,
        )

    def _validate_create_delivery_task_request(
        self,
        *,
        request_id,
        caregiver_id,
        item_id,
        quantity,
        destination_id,
        idempotency_key,
    ):
        checks = (
            (
                self._is_blank(request_id),
                self._invalid_request("request_id가 필요합니다.", "REQUEST_ID_INVALID"),
            ),
            (
                self._is_blank(caregiver_id),
                self._rejected("caregiver_id가 필요합니다.", "REQUESTER_NOT_AUTHORIZED"),
            ),
            (
                self._is_blank(item_id),
                self._invalid_request("item_id가 필요합니다.", "ITEM_ID_INVALID"),
            ),
            (
                quantity <= 0,
                self._invalid_request("quantity는 1 이상이어야 합니다.", "QUANTITY_INVALID"),
            ),
            (
                self._is_blank(destination_id),
                self._invalid_request("destination_id가 필요합니다.", "DESTINATION_ID_INVALID"),
            ),
            (
                self._is_blank(idempotency_key),
                self._invalid_request("idempotency_key가 필요합니다.", "IDEMPOTENCY_KEY_INVALID"),
            ),
        )

        for failed, response in checks:
            if failed:
                return response

        return None

    @staticmethod
    def _invalid_request(message: str, reason_code: str):
        return DeliveryRequestService._build_delivery_task_response(
            result_code=DeliveryRequestService.INVALID_REQUEST,
            result_message=message,
            reason_code=reason_code,
        )

    @staticmethod
    def _rejected(message: str, reason_code: str):
        return DeliveryRequestService._build_delivery_task_response(
            result_code=DeliveryRequestService.REJECTED,
            result_message=message,
            reason_code=reason_code,
        )

    @staticmethod
    def _build_delivery_task_response(
        *,
        result_code,
        result_message=None,
        reason_code=None,
        task_id=None,
        task_status=None,
        assigned_pinky_id=None,
    ):
        return {
            "result_code": result_code,
            "result_message": result_message,
            "reason_code": reason_code,
            "task_id": task_id,
            "task_status": task_status,
            "assigned_pinky_id": assigned_pinky_id,
        }

    @staticmethod
    def _is_blank(value) -> bool:
        return not str(value or "").strip()

    def _wire_delivery_destination_navigation_if_needed(self, *, response, destination_id):
        if response.get("result_code") != self.ACCEPTED:
            return

        if self.goal_pose_navigation_service is None:
            return

        if self.destination_goal_pose_resolver is None:
            return

        task_id = str(response.get("task_id") or "").strip()
        if not task_id:
            return

        goal_pose = self.destination_goal_pose_resolver(destination_id)
        if not goal_pose:
            return

        self.goal_pose_navigation_service.navigate(
            task_id=task_id,
            nav_phase="DELIVERY_DESTINATION",
            goal_pose=goal_pose,
            timeout_sec=self.delivery_navigation_timeout_sec,
        )

TaskRequestService = DeliveryRequestService

__all__ = ["DeliveryRequestService", "TaskRequestService"]
