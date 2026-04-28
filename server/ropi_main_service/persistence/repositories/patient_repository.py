from server.ropi_main_service.persistence.connection import fetch_all, fetch_one


class PatientRepository:
    def find_member_by_name_and_room(self, name: str, room_no: str):
        query = """
            SELECT
                member_id,
                member_name,
                room_no,
                admission_date
            FROM member
            WHERE member_name = %s
              AND room_no = %s
            LIMIT 1
        """
        return fetch_one(query, (name, room_no))

    def get_recent_events(self, member_id: str, limit: int = 20):
        query = """
            SELECT
                event_at,
                description,
                event_type_code,
                event_type_name,
                severity
            FROM member_event
            WHERE member_id = %s
            ORDER BY event_at DESC, member_event_id DESC
            LIMIT %s
        """
        return fetch_all(query, (member_id, limit))

    def get_preference(self, member_id: str):
        query = """
            SELECT
                preference,
                dislike,
                comment
            FROM preference
            WHERE member_id = %s
            LIMIT 1
        """
        return fetch_one(query, (member_id,))

    def get_prescriptions(self, member_id: str):
        query = """
            SELECT
                prescription_image_path AS image_path
            FROM prescription
            WHERE member_id = %s
            ORDER BY prescription_id DESC
        """
        return fetch_all(query, (member_id,))


__all__ = ["PatientRepository"]
