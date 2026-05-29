import typing as t
import enum

class AppCode(enum.IntEnum):
    SUCCESS = 0
    UNKNOWN_ERROR = 1
    NOT_FOUND = 2
    DATA_INVALID = 3
    TOKEN_INVALID = 10001
    TOKEN_EXPIRED = 10002
    PERMISSION_DENIED = 10003
    

def app_response(data: t.Optional[t.Any] = None, code: AppCode = AppCode.SUCCESS, msg: t.Optional[str] = None) -> t.Dict[str, t.Any]:
    if code == AppCode.SUCCESS:
        return {"code": code.value, "data": data}
    return {"code": code.value, "msg": msg}
