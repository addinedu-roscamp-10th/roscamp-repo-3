from server.ropi_main_service.persistence.repositories.user_repository import UserRepository


class AuthService:
    def __init__(self, repository=None):
        self.auth_repository = repository or UserRepository()

    def authenticate(self, login_id: str, password: str, role: str):
        try:
            normalized_role = (role or "").strip().lower()
            user = self.auth_repository.find_user_for_login(login_id, normalized_role)
            return self._build_auth_result(user, password, normalized_role)
        except Exception as exc:
            return False, f"로그인 처리 중 오류가 발생했습니다: {exc}"

    async def async_authenticate(self, login_id: str, password: str, role: str):
        try:
            normalized_role = (role or "").strip().lower()
            user = await self.auth_repository.async_find_user_for_login(login_id, normalized_role)
            return self._build_auth_result(user, password, normalized_role)
        except Exception as exc:
            return False, f"로그인 처리 중 오류가 발생했습니다: {exc}"

    @staticmethod
    def _build_auth_result(user, password: str, normalized_role: str):
        if not user:
            return False, "존재하지 않는 아이디입니다."

        db_password = str(user["user_password"])

        if db_password != password:
            return False, "비밀번호가 일치하지 않습니다."

        return True, {
            "user_id": str(user["user_id"]),
            "name": str(user["user_name"]),
            "role": normalized_role,
        }


__all__ = ["AuthService"]
