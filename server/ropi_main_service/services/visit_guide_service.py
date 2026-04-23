from server.ropi_db.repositories.visit_guide_repository import VisitGuideRepository


class VisitGuideService:
    def __init__(self):
        self.repository = VisitGuideRepository()

    def search_patient(self, keyword: str):
        keyword = (keyword or "").strip()
        if not keyword:
            return False, "검색어를 입력하세요.", None

        patient = self.repository.find_patient(keyword)
        if not patient:
            return False, "검색 결과가 없습니다.", None

        return True, "어르신 정보를 찾았습니다.", patient

    def start_robot_guide(self, patient: dict, member_id=None):
        if not patient:
            return False, "먼저 어르신을 검색하세요."

        return self.repository.create_robot_guide_event(
            patient_name=patient.get("name", "-"),
            room_no=patient.get("room", "-"),
            member_id=member_id,
        )


__all__ = ["VisitGuideService"]
