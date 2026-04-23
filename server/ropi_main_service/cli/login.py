import json
import sys

from server.ropi_main_service.application.auth import AuthService


def main():
    if len(sys.argv) != 4:
        print(json.dumps({
            "ok": False,
            "error": "로그인 실행 인자가 올바르지 않습니다."
        }, ensure_ascii=False))
        return 1

    login_id, password, role = sys.argv[1:4]
    ok, result = AuthService().authenticate(login_id, password, role)

    if ok:
        print(json.dumps({
            "ok": True,
            "session": result,
        }, ensure_ascii=False))
        return 0

    print(json.dumps({
        "ok": False,
        "error": str(result),
    }, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
