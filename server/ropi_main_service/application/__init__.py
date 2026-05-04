from importlib import import_module


_EXPORTS = {
    "AuthService": ("auth", "AuthService"),
    "CaregiverService": ("caregiver", "CaregiverService"),
    "DeliveryCancelService": ("delivery_cancel", "DeliveryCancelService"),
    "DeliveryOrchestrator": ("delivery_orchestrator", "DeliveryOrchestrator"),
    "DeliveryRequestService": ("task_request", "DeliveryRequestService"),
    "DeliveryRuntimeConfig": ("delivery_config", "DeliveryRuntimeConfig"),
    "DeliveryService": ("task_request", "DeliveryRequestService"),
    "DeliveryWorkflowTaskManager": ("delivery_workflow_task_manager", "DeliveryWorkflowTaskManager"),
    "FixedGoalPoseResolver": ("goal_pose_resolvers", "FixedGoalPoseResolver"),
    "FallEvidenceImageService": ("fall_evidence_image", "FallEvidenceImageService"),
    "FallResponseCommandService": ("fall_response_command", "FallResponseCommandService"),
    "GuideCommandService": ("guide_command", "GuideCommandService"),
    "GuideRuntimeService": ("guide_runtime", "GuideRuntimeService"),
    "GuideTrackingResultProcessor": ("guide_tracking_result", "GuideTrackingResultProcessor"),
    "GuideTrackingSnapshotStore": ("guide_tracking_snapshot", "GuideTrackingSnapshotStore"),
    "GuideTrackingUpdatePublisherService": (
        "guide_tracking_update",
        "GuideTrackingUpdatePublisherService",
    ),
    "GoalPoseNavigationService": ("goal_pose_navigation", "GoalPoseNavigationService"),
    "InventoryService": ("inventory", "InventoryService"),
    "KioskVisitorService": ("kiosk_visitor", "KioskVisitorService"),
    "MappedGoalPoseResolver": ("goal_pose_resolvers", "MappedGoalPoseResolver"),
    "ManipulationCommandService": ("manipulation_command", "ManipulationCommandService"),
    "PatientService": ("patient", "PatientService"),
    "PatrolResumeService": ("patrol_resume", "PatrolResumeService"),
    "PatrolTaskCreateService": ("patrol_task_create", "PatrolTaskCreateService"),
    "RosRuntimeReadinessService": ("runtime_readiness", "RosRuntimeReadinessService"),
    "StaffCallService": ("staff_call", "StaffCallService"),
    "TaskRequestService": ("task_request", "TaskRequestService"),
    "TaskMonitorService": ("task_monitor", "TaskMonitorService"),
    "VisitGuideService": ("visit_guide", "VisitGuideService"),
    "VisitorInfoService": ("visitor_info", "VisitorInfoService"),
    "VisitorRegisterService": ("visitor_register", "VisitorRegisterService"),
    "WorkflowTaskManager": ("workflow_task_manager", "WorkflowTaskManager"),
    "build_delivery_request_service": ("delivery_runtime", "build_delivery_request_service"),
    "build_patrol_request_service": ("patrol_runtime", "build_patrol_request_service"),
    "get_delivery_navigation_config": ("delivery_config", "get_delivery_navigation_config"),
    "get_delivery_runtime_config": ("delivery_config", "get_delivery_runtime_config"),
    "get_default_delivery_workflow_task_manager": (
        "delivery_workflow_task_manager",
        "get_default_delivery_workflow_task_manager",
    ),
    "get_default_workflow_task_manager": (
        "workflow_task_manager",
        "get_default_workflow_task_manager",
    ),
}


def __getattr__(name):
    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc

    module = import_module(f"{__name__}.{module_name}")
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value


__all__ = sorted(_EXPORTS)
