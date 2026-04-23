from server.ropi_db.repositories.patient_repository import PatientRepository


class PatientService:
    def __init__(self):
        self.repo = PatientRepository()

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
