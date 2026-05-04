from server.ropi_main_service.persistence.repositories.patient_repository import PatientRepository


class PatientService:
    def __init__(self, repository=None):
        self.repo = repository or PatientRepository()

    def search_patient_info(self, name: str, room_no: str):
        name = (name or "").strip()
        room_no = (room_no or "").strip()

        if not name or not room_no:
            raise ValueError("어르신 이름과 호실을 모두 입력해 주세요.")

        member = self.repo.find_member_by_name_and_room(name, room_no)
        if not member:
            return None

        member_id = member["member_id"]
        events = self.repo.get_recent_events(member_id, limit=20)
        preference = self.repo.get_preference(member_id) or {}
        prescriptions = self.repo.get_prescriptions(member_id)
        return self._format_patient_info(member, events, preference, prescriptions)

    def get_patient_info(self, member_id):
        member = self.repo.find_member_by_id(member_id)
        if not member:
            return None
        return self._build_patient_info(member)

    def search_patient_candidates(self, name: str = "", room_no: str = "", limit: int = 10):
        name = (name or "").strip()
        room_no = (room_no or "").strip()
        if not name and not room_no:
            return []
        rows = self.repo.list_member_candidates(name=name, room_no=room_no, limit=limit)
        return [self._format_candidate(row) for row in rows]

    async def async_search_patient_info(self, name: str, room_no: str):
        name = (name or "").strip()
        room_no = (room_no or "").strip()

        if not name or not room_no:
            raise ValueError("어르신 이름과 호실을 모두 입력해 주세요.")

        member = await self.repo.async_find_member_by_name_and_room(name, room_no)
        if not member:
            return None

        member_id = member["member_id"]
        events = await self.repo.async_get_recent_events(member_id, limit=20)
        preference = await self.repo.async_get_preference(member_id) or {}
        prescriptions = await self.repo.async_get_prescriptions(member_id)
        return self._format_patient_info(member, events, preference, prescriptions)

    async def async_get_patient_info(self, member_id):
        member = await self.repo.async_find_member_by_id(member_id)
        if not member:
            return None
        return await self._async_build_patient_info(member)

    async def async_search_patient_candidates(
        self,
        name: str = "",
        room_no: str = "",
        limit: int = 10,
    ):
        name = (name or "").strip()
        room_no = (room_no or "").strip()
        if not name and not room_no:
            return []
        rows = await self.repo.async_list_member_candidates(
            name=name,
            room_no=room_no,
            limit=limit,
        )
        return [self._format_candidate(row) for row in rows]

    def _build_patient_info(self, member):
        member_id = member["member_id"]
        events = self.repo.get_recent_events(member_id, limit=20)
        preference = self.repo.get_preference(member_id) or {}
        prescriptions = self.repo.get_prescriptions(member_id)
        return self._format_patient_info(member, events, preference, prescriptions)

    async def _async_build_patient_info(self, member):
        member_id = member["member_id"]
        events = await self.repo.async_get_recent_events(member_id, limit=20)
        preference = await self.repo.async_get_preference(member_id) or {}
        prescriptions = await self.repo.async_get_prescriptions(member_id)
        return self._format_patient_info(member, events, preference, prescriptions)

    @staticmethod
    def _format_candidate(row):
        return {
            "member_id": row.get("member_id"),
            "name": row.get("member_name") or "",
            "room_no": row.get("room_no") or "",
            "admission_date": row.get("admission_date"),
        }

    @staticmethod
    def _format_patient_info(member, events, preference, prescriptions):
        member_id = member["member_id"]
        return {
            "member_id": member_id,
            "name": member.get("member_name") or "",
            "room_no": member.get("room_no") or "",
            "admission_date": member.get("admission_date"),
            "preference": preference.get("preference") or "-",
            "dislike": preference.get("dislike") or "-",
            "comment": preference.get("comment") or "-",
            "events": [
                {
                    "event_at": row.get("event_at"),
                    "description": row.get("description") or "",
                }
                for row in events
            ],
            "prescription_paths": [
                row.get("image_path") or ""
                for row in prescriptions
                if row.get("image_path")
            ],
        }


__all__ = ["PatientService"]
