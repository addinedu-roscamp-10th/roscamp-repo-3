from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def nonempty_lines(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class GuideInterfaceContractTest(unittest.TestCase):
    def test_guide_command_request_matches_control_handoff_contract(self) -> None:
        service_text = (ROOT / "srv/GuideCommand.srv").read_text(encoding="utf-8")
        request_text, response_text = service_text.split("---", maxsplit=1)
        request_lines = [
            line.strip()
            for line in request_text.splitlines()
            if line.strip()
        ]
        response_lines = [
            line.strip()
            for line in response_text.splitlines()
            if line.strip()
        ]

        self.assertEqual(
            request_lines,
            [
                "string task_id",
                "string command_type",
                "int32 target_track_id",
                "string destination_id",
                "geometry_msgs/PoseStamped destination_pose",
            ],
        )
        self.assertEqual(
            response_lines,
            [
                "bool accepted",
                "string reason_code",
                "string message",
            ],
        )

    def test_guide_phase_snapshot_matches_if_gui_007_payload(self) -> None:
        self.assertEqual(
            nonempty_lines(ROOT / "msg/GuidePhaseSnapshot.msg"),
            [
                "string task_id",
                "string pinky_id",
                "string guide_phase",
                "int32 target_track_id",
                "string reason_code",
                "uint32 seq",
                "builtin_interfaces/Time occurred_at",
            ],
        )

    def test_retired_tracking_update_message_is_not_exported(self) -> None:
        self.assertFalse((ROOT / "msg/GuideTrackingUpdate.msg").exists())
        cmake_text = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        self.assertNotIn("GuideTrackingUpdate", cmake_text)


if __name__ == "__main__":
    unittest.main()
