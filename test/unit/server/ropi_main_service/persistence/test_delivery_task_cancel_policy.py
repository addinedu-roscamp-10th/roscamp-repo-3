import json

from server.ropi_main_service.persistence.repositories.delivery_task_cancel_policy import (
    DeliveryTaskCancelPolicy,
)


def build_running_row():
    return {
        "task_id": 101,
        "task_status": "RUNNING",
        "phase": "DELIVERY_PICKUP",
        "assigned_robot_id": "pinky2",
    }


def test_cancel_policy_builds_cancel_target_response_for_cancellable_task():
    response = DeliveryTaskCancelPolicy().build_cancel_target_response(
        build_running_row(),
        task_id=101,
    )

    assert response == {
        "result_code": "ACCEPTED",
        "result_message": None,
        "reason_code": None,
        "task_id": 101,
        "task_status": "RUNNING",
        "assigned_robot_id": "pinky2",
    }


def test_cancel_policy_rejects_terminal_cancel_target():
    response = DeliveryTaskCancelPolicy().build_cancel_target_response(
        {
            **build_running_row(),
            "task_status": "COMPLETED",
        },
        task_id=101,
    )

    assert response["result_code"] == "REJECTED"
    assert response["reason_code"] == "TASK_NOT_CANCELLABLE"
    assert response["task_status"] == "COMPLETED"


def test_cancel_policy_builds_cancel_requested_write_plan():
    cancel_response = {
        "result_code": "CANCEL_REQUESTED",
        "result_message": "action cancel request was accepted.",
        "cancel_requested": True,
    }

    plan = DeliveryTaskCancelPolicy().build_cancel_result_write_plan(
        row=build_running_row(),
        cancel_response=cancel_response,
    )

    assert plan["task_status"] == "CANCEL_REQUESTED"
    assert plan["update_params"] == (
        "USER_CANCEL_REQUESTED",
        "CANCEL_REQUESTED",
        "action cancel request was accepted.",
        101,
    )
    assert plan["history_params"] == (
        101,
        "RUNNING",
        "DELIVERY_PICKUP",
        "USER_CANCEL_REQUESTED",
        "action cancel request was accepted.",
        "control_service",
    )
    assert plan["event_params"][1:7] == (
        "DELIVERY_TASK_CANCEL_REQUESTED",
        "INFO",
        "pinky2",
        "CANCEL_REQUESTED",
        "USER_CANCEL_REQUESTED",
        "action cancel request was accepted.",
    )
    assert json.loads(plan["event_params"][7]) == cancel_response


def test_cancel_policy_builds_cancelled_workflow_plan():
    workflow_response = {
        "result_code": "FAILED",
        "result_message": "goal canceled by user request.",
        "status": 5,
    }

    plan = DeliveryTaskCancelPolicy().build_cancelled_result_write_plan(
        row={
            **build_running_row(),
            "task_status": "CANCEL_REQUESTED",
            "phase": "CANCEL_REQUESTED",
        },
        workflow_response=workflow_response,
    )

    assert plan["task_status"] == "CANCELLED"
    assert plan["reason_code"] == "ROS_ACTION_CANCELLED"
    assert plan["update_params"] == (
        "ROS_ACTION_CANCELLED",
        "CANCELLED",
        "goal canceled by user request.",
        101,
    )
    assert plan["event_params"][1:7] == (
        "DELIVERY_TASK_CANCELLED",
        "INFO",
        "pinky2",
        "CANCELLED",
        "ROS_ACTION_CANCELLED",
        "goal canceled by user request.",
    )
    assert json.loads(plan["event_params"][7]) == workflow_response


def test_cancel_policy_guards_cancelled_result_until_cancel_requested():
    response = DeliveryTaskCancelPolicy().build_cancelled_result_guard(
        build_running_row(),
        task_id=101,
        workflow_response={"result_code": "FAILED"},
    )

    assert response["result_code"] == "IGNORED"
    assert response["reason_code"] == "TASK_NOT_CANCEL_REQUESTED"
    assert response["task_status"] == "RUNNING"
