from server.ropi_main_service.ros.command_dispatcher import (
    ACTION_COMMAND_SPECS,
    SERVICE_COMMAND_SPECS,
)


def test_action_command_specs_define_ros_action_contracts():
    assert set(ACTION_COMMAND_SPECS) == {
        "navigate_to_goal",
        "execute_manipulation",
        "execute_patrol_path",
    }

    navigation = ACTION_COMMAND_SPECS["navigate_to_goal"]
    assert navigation.client_attr == "goal_pose_action_client"
    assert navigation.identifier_field == "pinky_id"
    assert navigation.action_name_template == "/ropi/control/{identifier}/navigate_to_goal"
    assert navigation.timeout_strategy == "navigation"

    manipulation = ACTION_COMMAND_SPECS["execute_manipulation"]
    assert manipulation.client_attr == "manipulation_action_client"
    assert manipulation.identifier_field == "arm_id"
    assert manipulation.action_name_template == "/ropi/arm/{identifier}/execute_manipulation"
    assert manipulation.timeout_strategy == "manipulation"

    patrol = ACTION_COMMAND_SPECS["execute_patrol_path"]
    assert patrol.client_attr == "patrol_path_action_client"
    assert patrol.identifier_field == "pinky_id"
    assert patrol.action_name_template == "/ropi/control/{identifier}/execute_patrol_path"
    assert patrol.timeout_strategy == "navigation"


def test_service_command_specs_define_ros_service_contracts():
    assert set(SERVICE_COMMAND_SPECS) == {
        "fall_response_control",
        "guide_command",
    }

    fall_response = SERVICE_COMMAND_SPECS["fall_response_control"]
    assert fall_response.client_attr == "fall_response_control_client"
    assert fall_response.pinky_id_getter == "_get_fall_response_pinky_id"
    assert fall_response.request_builder == "_build_fall_response_request"
    assert fall_response.service_name_builder == "_build_fall_response_service_name"

    guide = SERVICE_COMMAND_SPECS["guide_command"]
    assert guide.client_attr == "guide_command_client"
    assert guide.pinky_id_getter == "_get_guide_pinky_id"
    assert guide.request_builder == "_build_guide_command_request"
    assert guide.service_name_builder == "_build_guide_command_service_name"
