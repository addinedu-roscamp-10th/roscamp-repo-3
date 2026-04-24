from pathlib import Path
import xml.etree.ElementTree as ET


REPO_ROOT = Path(__file__).resolve().parents[2]
PINKY_LED_SERVER = (
    REPO_ROOT
    / "device"
    / "ropi_mobile"
    / "pinky_pro"
    / "src"
    / "pinky_pro"
    / "pinky_led"
    / "pinky_led"
    / "led_server.py"
)
PINKY_EMOTION_SERVER = (
    REPO_ROOT
    / "device"
    / "ropi_mobile"
    / "pinky_pro"
    / "src"
    / "pinky_pro"
    / "pinky_emotion"
    / "pinky_emotion"
    / "emotion_server.py"
)
PINKY_EMOTION_MAIN = (
    REPO_ROOT
    / "device"
    / "ropi_mobile"
    / "pinky_pro"
    / "src"
    / "pinky_pro"
    / "pinky_emotion"
    / "pinky_emotion"
    / "pinky_emotion.py"
)
PINKY_LED_PACKAGE = (
    REPO_ROOT
    / "device"
    / "ropi_mobile"
    / "pinky_pro"
    / "src"
    / "pinky_pro"
    / "pinky_led"
    / "package.xml"
)
PINKY_EMOTION_PACKAGE = (
    REPO_ROOT
    / "device"
    / "ropi_mobile"
    / "pinky_pro"
    / "src"
    / "pinky_pro"
    / "pinky_emotion"
    / "package.xml"
)
PINKY_README = (
    REPO_ROOT
    / "device"
    / "ropi_mobile"
    / "pinky_pro"
    / "src"
    / "pinky_pro"
    / "README.md"
)
DELIVERY_ROPI_INTERFACE_PACKAGE = (
    REPO_ROOT
    / "pinky_pro_delivery"
    / "src"
    / "ropi_interface"
    / "package.xml"
)


def test_workspace_runtime_python_uses_ropi_interface_imports():
    for file_path in (PINKY_LED_SERVER, PINKY_EMOTION_SERVER, PINKY_EMOTION_MAIN):
        content = file_path.read_text(encoding="utf-8")
        assert "from ropi_interface.srv import" in content
        assert "pinky_interfaces" not in content


def test_workspace_python_packages_declare_ropi_interface_dependency():
    for file_path in (PINKY_LED_PACKAGE, PINKY_EMOTION_PACKAGE):
        content = file_path.read_text(encoding="utf-8")
        assert "<depend>ropi_interface</depend>" in content or "<exec_depend>ropi_interface</exec_depend>" in content


def test_workspace_readme_examples_use_ropi_interface_service_types():
    content = PINKY_README.read_text(encoding="utf-8")
    assert "ropi_interface/srv/SetLed" in content
    assert "ropi_interface/srv/SetBrightness" in content
    assert "ropi_interface/srv/Emotion" in content
    assert "pinky_interfaces/srv/" not in content


def test_delivery_workspace_ropi_interface_package_is_ament_cmake():
    root = ET.fromstring(DELIVERY_ROPI_INTERFACE_PACKAGE.read_text(encoding="utf-8"))
    assert root.findtext("buildtool_depend") == "ament_cmake"
    buildtool_depends = [elem.text for elem in root.findall("buildtool_depend")]
    assert "rosidl_default_generators" in buildtool_depends
    assert root.findtext("member_of_group") == "rosidl_interface_packages"

    export = root.find("export")
    assert export is not None
    assert export.findtext("build_type") == "ament_cmake"
