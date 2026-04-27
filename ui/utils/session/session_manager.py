from dataclasses import dataclass
from typing import Optional


@dataclass
class UserSession:
    user_id: str
    name: str
    role: str

class SessionManager:
    _current_user: Optional[UserSession] = None

    @classmethod
    def login(cls, user: UserSession) -> None:
        cls._current_user = user

    @classmethod
    def logout(cls) -> None:
        cls._current_user = None

    @classmethod
    def current_user(cls) -> Optional[UserSession]:
        return cls._current_user

    @classmethod
    def is_authenticated(cls) -> bool:
        return cls._current_user is not None