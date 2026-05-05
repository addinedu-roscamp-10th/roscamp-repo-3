from server.ropi_main_service.application.caregiver_rpc_facade import (
    CaregiverRpcFacade,
)
from server.ropi_main_service.application.coordinate_config import CoordinateConfigService
from server.ropi_main_service.application.fall_evidence_image import (
    FallEvidenceImageService,
)
from server.ropi_main_service.application.fms_config import FmsConfigService
from server.ropi_main_service.application.inventory import InventoryService
from server.ropi_main_service.application.kiosk_visitor import KioskVisitorService
from server.ropi_main_service.application.patient import PatientService
from server.ropi_main_service.application.staff_call import StaffCallService
from server.ropi_main_service.application.task_monitor import TaskMonitorService
from server.ropi_main_service.application.task_request import TaskRequestService
from server.ropi_main_service.application.visit_guide import VisitGuideService
from server.ropi_main_service.application.visitor_info import VisitorInfoService
from server.ropi_main_service.application.visitor_register import VisitorRegisterService


def build_rpc_service_registry():
    return {
        "caregiver": CaregiverRpcFacade,
        "coordinate_config": CoordinateConfigService,
        "fms_config": FmsConfigService,
        "patient": PatientService,
        "inventory": InventoryService,
        "kiosk_visitor": KioskVisitorService,
        "fall_evidence_image": FallEvidenceImageService,
        "task_monitor": TaskMonitorService,
        "task_request": TaskRequestService,
        "visit_guide": VisitGuideService,
        "visitor_info": VisitorInfoService,
        "visitor_register": VisitorRegisterService,
        "staff_call": StaffCallService,
    }


SERVICE_REGISTRY = build_rpc_service_registry()


__all__ = ["SERVICE_REGISTRY", "build_rpc_service_registry"]
