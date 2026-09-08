import typing as t

from aiohttp import web
from sqlalchemy import select

from database.base import async_session
from database.model import Account
from cores.exchange.binance.api.basic.api_permission import ApiPermission
from cores.exchange.binance.binance import Binance
from cores.trader import trader_names
from utils.middleware.auth import auth
from utils.middleware.type_checker import json_post_checker
from utils.types import AppCode, app_response

# 允许置空（null）的字段
_NULLABLE_FIELDS = {"api_passphrase", "strategy_uuid", "trader"}


def _account_to_dict(acc: Account) -> dict[str, t.Any]:
    return {
        "id": acc.id,
        "name": acc.name,
        "exchange": acc.exchange,
        "api_key": acc.api_key,
        "api_secret": acc.api_secret,
        "api_passphrase": acc.api_passphrase,
        "encrypt_type": acc.encrypt_type,
        "strategy_uuid": acc.strategy_uuid,
        "status": acc.status,
        "trader": acc.trader,
        "period": acc.period,
        "target": acc.target,
    }


@auth(perm=["account.read"])
async def list_accounts(request: web.Request):
    async with async_session() as s:
        rows = (await s.execute(select(Account))).scalars().all()
    return web.json_response(app_response(data=[_account_to_dict(a) for a in rows]))


@auth(perm=["account.read"])
async def list_traders(request: web.Request):
    """获取可用的执行器名称列表。"""
    return web.json_response(app_response(data=trader_names()))


@auth(perm=["account.read"])
async def get_account(request: web.Request):
    match_info = t.cast(dict[str, t.Any], request.match_info)
    try:
        account_id = int(match_info["id"])
    except (ValueError, KeyError):
        return web.json_response(app_response(code=AppCode.DATA_INVALID, msg="id 必须为整数"))
    async with async_session() as s:
        acc = (await s.execute(select(Account).filter_by(id=account_id))).scalar()
    if acc is None:
        return web.json_response(app_response(code=AppCode.NOT_FOUND, msg="账号不存在"))
    return web.json_response(app_response(data=_account_to_dict(acc)))


@auth(perm=["account.write"])
@json_post_checker(
    necessary_keys={"name": str, "exchange": str},
    optional_keys={"api_key": str, "api_secret": str, "api_passphrase": str,
                   "encrypt_type": str, "strategy_uuid": str, "trader": str,
                   "period": int, "target": str},
)
async def create_account(request: web.Request, data: dict[str, t.Any] | None = None):
    if data is None:
        return web.json_response(app_response(code=AppCode.DATA_INVALID, msg="data is None"))
    async with async_session() as s:
        try:
            existing = (await s.execute(select(Account).filter_by(name=data["name"]))).scalar()
            if existing is not None:
                return web.json_response(
                    app_response(code=AppCode.DATA_INVALID, msg=f"账号 '{data['name']}' 已存在")
                )
            acc = Account(
                name=data["name"],
                exchange=data["exchange"],
                api_key=data.get("api_key") or "",
                api_secret=data.get("api_secret") or "",
                api_passphrase=data.get("api_passphrase"),
                encrypt_type=data.get("encrypt_type", "hmac"),
                strategy_uuid=data.get("strategy_uuid"),
                status=1,
                trader=data.get("trader"),
                period=data.get("period", 60),
                target=data.get("target", "[]"),
            )
            s.add(acc)
            await s.commit()
        except Exception as e:  # noqa: BLE001
            await s.rollback()
            return web.json_response(app_response(code=AppCode.UNKNOWN_ERROR, msg=str(e)))
    return web.json_response(app_response(data=_account_to_dict(acc)))


@auth(perm=["account.write"])
@json_post_checker(
    necessary_keys={"id": int},
    optional_keys={"name": str, "exchange": str, "api_key": str, "api_secret": str,
                   "api_passphrase": str, "encrypt_type": str, "strategy_uuid": str,
                   "trader": str, "period": int, "target": str},
)
async def update_account(request: web.Request, data: dict[str, t.Any] | None = None):
    if data is None:
        return web.json_response(app_response(code=AppCode.DATA_INVALID, msg="data is None"))
    async with async_session() as s:
        try:
            acc = (await s.execute(select(Account).filter_by(id=data["id"]))).scalar()
            if acc is None:
                return web.json_response(app_response(code=AppCode.NOT_FOUND, msg="账号不存在"))
            for field in ("name", "exchange", "api_key", "api_secret", "api_passphrase",
                          "encrypt_type", "strategy_uuid", "trader", "period", "target"):
                if field not in data:
                    continue
                if field in _NULLABLE_FIELDS:
                    setattr(acc, field, data[field])
                elif data[field] is not None:
                    setattr(acc, field, data[field])
            await s.commit()
        except Exception as e:  # noqa: BLE001
            await s.rollback()
            return web.json_response(app_response(code=AppCode.UNKNOWN_ERROR, msg=str(e)))
    return web.json_response(app_response(data=_account_to_dict(acc)))


@auth(perm=["account.write"])
@json_post_checker(necessary_keys={"id": int, "status": int})
async def set_account_status(request: web.Request, data: dict[str, t.Any] | None = None):
    """独立修改账号执行状态（启动为执行中时校验策略配置与交易所连接）。"""
    if data is None:
        return web.json_response(app_response(code=AppCode.DATA_INVALID, msg="data is None"))
    status = data["status"]
    if status not in (0, 1):
        return web.json_response(app_response(code=AppCode.DATA_INVALID, msg="status 必须为 0 或 1"))
    async with async_session() as s:
        try:
            acc = (await s.execute(select(Account).filter_by(id=data["id"]))).scalar()
            if acc is None:
                return web.json_response(app_response(code=AppCode.NOT_FOUND, msg="账号不存在"))
            if status == 0:  # 启动为执行中
                # 检查是否配置了策略
                if not t.cast(str | None, acc.strategy_uuid):
                    return web.json_response(
                        app_response(code=AppCode.DATA_INVALID, msg="请先为该账号绑定策略")
                    )
                # 检查交易所连接与 API Key 权限
                if t.cast(str, acc.exchange) == "binance":
                    encrypt_t = t.cast(
                        t.Literal['hmac', 'ed25519', 'rsa'], acc.encrypt_type or 'hmac'
                    )
                    b = Binance(
                        t.cast(str, acc.api_key),
                        t.cast(str, acc.api_secret),
                        encrypt_t,
                    )
                    try:
                        ok, perm = await b.request(ApiPermission())
                        if not ok:
                            return web.json_response(
                                app_response(code=AppCode.EXECUTE_FAILED, msg="无法连接币安交易所或 API Key 无效")
                            )
                        if not (perm.get("permitsUniversalTransfer")
                                and perm.get("enableSpotAndMarginTrading")
                                and perm.get("enableFutures")):
                            return web.json_response(
                                app_response(code=AppCode.PERMISSION_DENIED,
                                             msg="API Key 缺少所需权限（划转/现货/合约）")
                            )
                    finally:
                        await b.session.close()
            setattr(acc, 'status', status)
            await s.commit()
        except Exception as e:  # noqa: BLE001
            await s.rollback()
            return web.json_response(app_response(code=AppCode.UNKNOWN_ERROR, msg=str(e)))
    return web.json_response(app_response(data=_account_to_dict(acc)))


@auth(perm=["account.write"])
@json_post_checker(necessary_keys={"id": int})
async def delete_account(request: web.Request, data: dict[str, t.Any] | None = None):
    if data is None:
        return web.json_response(app_response(code=AppCode.DATA_INVALID, msg="data is None"))
    async with async_session() as s:
        try:
            acc = (await s.execute(select(Account).filter_by(id=data["id"]))).scalar()
            if acc is None:
                return web.json_response(app_response(code=AppCode.NOT_FOUND, msg="账号不存在"))
            # 执行中状态不可删除
            if t.cast(int, acc.status) == 0:
                return web.json_response(
                    app_response(code=AppCode.DATA_INVALID, msg="账号处于执行中状态，请先暂停后再删除")
                )
            await s.delete(acc)
            await s.commit()
        except Exception as e:  # noqa: BLE001
            await s.rollback()
            return web.json_response(app_response(code=AppCode.UNKNOWN_ERROR, msg=str(e)))
    return web.json_response(app_response(msg="账号已删除"))


rules = [
    web.RouteDef("GET", "/account/list", list_accounts, {}),
    web.RouteDef("GET", "/account/{id}", get_account, {}),
    web.RouteDef("POST", "/account/create", create_account, {}),
    web.RouteDef("POST", "/account/update", update_account, {}),
    web.RouteDef("POST", "/account/status", set_account_status, {}),
    web.RouteDef("POST", "/account/delete", delete_account, {}),
    web.RouteDef("GET", "/trader/list", list_traders, {}),
]
