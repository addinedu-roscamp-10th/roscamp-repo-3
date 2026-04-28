from importlib import import_module


_EXPORTS = {
    "AuthService": ("auth", "AuthService"),
    "CaregiverService": ("caregiver", "CaregiverService"),
    "DeliveryOrchestrator": ("delivery_orchestrator", "DeliveryOrchestrator"),
    "DeliveryRequestService": ("task_request", "DeliveryRequestService"),
    "DeliveryRuntimeConfig": ("delivery_config", "DeliveryRuntimeConfig"),
    "DeliveryService": ("task_request", "DeliveryRequestService"),
    "DeliveryWorkflowTaskManager": ("delivery_workflow_task_manager", "DeliveryWorkflowTaskManager"),
    "FixedGoalPoseResolver": ("goal_pose_resolvers", "FixedGoalPoseResolver"),
    "GoalPoseNavigationService": ("goal_pose_navigation", "GoalPoseNavigationService"),
    "InventoryService": ("inventory", "InventoryService"),
    "MappedGoalPoseResolver": ("goal_pose_resolvers", "MappedGoalPoseResolver"),
    "ManipulationCommandService": ("manipulation_command", "ManipulationCommandService"),
    "PatientService": ("patient", "PatientService"),
    "RosRuntimeReadinessService": ("runtime_readiness", "RosRuntimeReadinessService"),
    "StaffCallService": ("staff_call", "StaffCallService"),
    "TaskRequestService": ("task_request", "TaskRequestService"),
    "VisitGuideService": ("visit_guide", "VisitGuideService"),
    "VisitorInfoService": ("visitor_info", "VisitorInfoService"),
    "VisitorRegisterService": ("visitor_register", "VisitorRegisterService"),
    "build_delivery_request_service": ("delivery_runtime", "build_delivery_request_service"),
    "get_delivery_navigation_config": ("delivery_config", "get_delivery_navigation_config"),
    "get_delivery_runtime_config": ("delivery_config", "get_delivery_runtime_config"),
    "get_default_delivery_workflow_task_manager": (
        "delivery_workflow_task_manager",
        "get_default_delivery_workflow_task_manager",
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
