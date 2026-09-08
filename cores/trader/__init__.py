from .base import TraderInterface, BaseTrader, extract_signals
import typing as t

_traders: dict[str, t.Type[TraderInterface]] = {
    'default': BaseTrader
}

def get_trader(name: str) -> t.Type[TraderInterface]:
    return _traders.get(name, BaseTrader)

def trader_names() -> list[str]:
    """返回所有已注册执行器的名称。"""
    return list(_traders.keys())