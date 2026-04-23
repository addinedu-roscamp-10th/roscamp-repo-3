from .auth import AuthService
from .caregiver import CaregiverService
from .goal_pose_navigation import GoalPoseNavigationService
from .inventory import InventoryService
from .patient import PatientService
from .staff_call import StaffCallService
from .task_request import DeliveryRequestService, TaskRequestService
from .visit_guide import VisitGuideService
from .visitor_info import VisitorInfoService
from .visitor_register import VisitorRegisterService

DeliveryService = DeliveryRequestService

__all__ = [
    "AuthService",
    "CaregiverService",
    "DeliveryRequestService",
    "DeliveryService",
    "GoalPoseNavigationService",
    "InventoryService",
    "PatientService",
    "StaffCallService",
    "TaskRequestService",
    "VisitGuideService",
    "VisitorInfoService",
    "VisitorRegisterService",
]
