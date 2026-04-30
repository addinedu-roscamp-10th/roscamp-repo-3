from server.ropi_main_service.application.workflow_task_manager import (
    WorkflowTaskManager,
    get_default_workflow_task_manager,
)


DeliveryWorkflowTaskManager = WorkflowTaskManager
get_default_delivery_workflow_task_manager = get_default_workflow_task_manager


__all__ = [
    "DeliveryWorkflowTaskManager",
    "get_default_delivery_workflow_task_manager",
]
