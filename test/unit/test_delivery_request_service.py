import unittest
from unittest.mock import patch

from server.ropi_main_service.services.task_request_service import DeliveryRequestService


class DeliveryRequestServiceContractTest(unittest.TestCase):
    def test_submit_delivery_request_requires_member_id(self):
        with patch("server.ropi_main_service.services.task_request_service.DeliveryRequestRepository") as repository_cls:
            service = DeliveryRequestService()

            ok, message = service.submit_delivery_request(
                item_name="물티슈",
                quantity=1,
                destination="305호",
                priority="일반",
                detail="운반 테스트",
                member_id="",
            )

        self.assertFalse(ok)
        self.assertEqual(message, "로그인 사용자 정보가 없습니다.")
        repository_cls.return_value.create_delivery_request.assert_not_called()

    def test_submit_delivery_request_forwards_valid_payload_to_repository(self):
        with patch("server.ropi_main_service.services.task_request_service.DeliveryRequestRepository") as repository_cls:
            repository_cls.return_value.create_delivery_request.return_value = (True, "물품 요청이 접수되었습니다.")
            service = DeliveryRequestService()

            result = service.submit_delivery_request(
                item_name="물티슈",
                quantity=2,
                destination="305호",
                priority="긴급",
                detail="운반 테스트",
                member_id="MEM001",
            )

        self.assertEqual(result, (True, "물품 요청이 접수되었습니다."))
        repository_cls.return_value.create_delivery_request.assert_called_once_with(
            item_name="물티슈",
            quantity=2,
            destination="305호",
            priority="긴급",
            detail="운반 테스트",
            member_id="MEM001",
        )


if __name__ == "__main__":
    unittest.main()
