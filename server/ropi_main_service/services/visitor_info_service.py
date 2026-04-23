from server.ropi_db.repositories.visitor_info_repository import VisitorInfoRepository


class VisitorInfoService:
    def __init__(self):
        self.repository = VisitorInfoRepository()

    def get_patient_visit_info(self, keyword: str):
        keyword = (keyword or "").strip()
        if not keyword:
            return False, "이름 또는 병실을 입력하세요.", None

        result = self.repository.get_visitor_patient_info(keyword)
        if not result:
            return False, "조회 결과가 없습니다.", None

        return True, "면회 정보를 조회했습니다.", result


__all__ = ["VisitorInfoService"]
