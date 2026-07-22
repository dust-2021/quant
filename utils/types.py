import typing as t
import enum
from loguru import logger

class AppCode(enum.IntEnum):
    SUCCESS = 0
    UNKNOWN_ERROR = 1
    NOT_FOUND = 2
    DATA_INVALID = 3
    TOKEN_INVALID = 10001
    TOKEN_EXPIRED = 10002
    PERMISSION_DENIED = 10003
    
    DATA_NOT_READY = 20001
    EXECUTE_FAILED = 20002
    

def app_response(data: t.Optional[t.Any] = None, code: AppCode = AppCode.SUCCESS, msg: t.Optional[str] = None) -> t.Dict[str, t.Any]:
    if code == AppCode.SUCCESS:
        return {"code": code.value, "data": data}
    return {"code": code.value, "msg": msg}


class SingletonMeta(type):
    """线程安全的单例元类"""
    _instances: t.Dict[type, object] = {}
    
    def __call__(cls, *args: t.Any, **kwargs: t.Any) -> t.Any:
        if cls not in cls._instances:
            # 调用父类 type 的 __call__，它会自动处理 __new__ 和 __init__
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
            logger.info(f'create singleton of {cls.__name__}')
        return cls._instances[cls]
    
    @classmethod
    def get_instance(cls, class_type: type) -> t.Optional[object]:
        """获取已创建的实例（用于调试）"""
        return cls._instances.get(class_type)