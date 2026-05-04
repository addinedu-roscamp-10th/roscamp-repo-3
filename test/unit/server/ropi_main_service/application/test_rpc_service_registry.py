from server.ropi_main_service.application.caregiver_rpc_facade import (
    CaregiverRpcFacade,
)
from server.ropi_main_service.application.coordinate_config import CoordinateConfigService
from server.ropi_main_service.application.rpc_service_registry import (
    SERVICE_REGISTRY,
    build_rpc_service_registry,
)
from server.ropi_main_service.application.task_request import TaskRequestService
from server.ropi_main_service.application.visit_guide import VisitGuideService


def test_rpc_service_registry_exposes_phase1_service_names():
    registry = build_rpc_service_registry()

    assert set(registry) == {
        "caregiver",
        "coordinate_config",
        "patient",
        "inventory",
        "kiosk_visitor",
        "fall_evidence_image",
        "task_monitor",
        "task_request",
        "visit_guide",
        "visitor_info",
        "visitor_register",
        "staff_call",
    }


def test_rpc_service_registry_maps_core_services_to_application_factories():
    registry = build_rpc_service_registry()

    assert registry["caregiver"] is CaregiverRpcFacade
    assert registry["coordinate_config"] is CoordinateConfigService
    assert registry["task_request"] is TaskRequestService
    assert registry["visit_guide"] is VisitGuideService


def test_global_service_registry_uses_built_mapping():
    assert SERVICE_REGISTRY == build_rpc_service_registry()
