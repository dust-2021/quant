import enum
import typing as t

from loguru import logger
import numpy as np


class AppCode(enum.IntEnum):
    """
    http 自定义状态码
    """
    
    SUCCESS = 0
    UNKNOWN_ERROR = 1
    NOT_FOUND = 2
    DATA_INVALID = 3
    TOKEN_INVALID = 10001
    TOKEN_EXPIRED = 10002
    PERMISSION_DENIED = 10003
    
    DATA_NOT_READY = 20001
    EXECUTE_FAILED = 20002
    

def app_response(data: t.Any | None = None, code: AppCode = AppCode.SUCCESS, msg: str | None = None) -> dict[str, t.Any]:
    if code == AppCode.SUCCESS:
        return {"code": code.value, "data": data}
    return {"code": code.value, "msg": msg}


class Permission(enum.Enum):
    
    STRATEGY_READ = 'STRATEGY_READ'
    STRATEGY_WRITE = 'STRATEGY_WRITE'
    

class Runner_Res(t.TypedDict):
    """
    回测执行器返回dict的类型规范
    """
    
    startTime: int
    endTime: int
    target: t.Sequence[str] | str
    period: int
    params: dict[str, t.Any]
    liquidation: int | None
    premium: float
    data: str | None
    maximumDrawdown: float
    netValue: float
    annualizedRateOfReturn: float
    monthlyRateOfReturn: float
    tradeData: str

    # ==== default runner keys ====
    tradeCount: t.NotRequired[int]
    winRate: t.NotRequired[float]
    maximumLoss: t.NotRequired[float]
    maximumProfit: t.NotRequired[float]
    averageProfitLossRatio: t.NotRequired[float | None]
    
    
class CacheName(enum.Enum):
    """
    缓存数据名前缀
    """
    
    Binance_Kline = 'binance_kline'
    Binance_ExchangeInfo = 'binance_exchangeInfo'
    Binance_ExchangeInfo_Future = 'binance_exchangeInfo_future'
    Binance_Api_Limit = 'Binance_Api_Limit'
    
    
class CustomError(Exception):
    """"""


class ContextBase(t.TypedDict):
    """
    上下文规范
    """
    is_living: bool
    target: str | t.Sequence[str] | None
    period: t.Literal[60, 3600, 86400]

    # 回测设置
    start_time: t.NotRequired[int]
    end_time: t.NotRequired[int]

    # 实盘设置
    excute_strict_time: t.NotRequired[int]
    strategy_uuid: t.NotRequired[str]
    exchange: t.NotRequired[str]
    signal_name: t.NotRequired[str]
    
    