from aiohttp import web
from sqlalchemy import select, text
from database.data_center import get_session
from database.base import DataPeriod, async_session as dc_async_session
from database.model import Exchange, Script, Target
from utils.types import app_response, AppCode
from utils.middleware.type_checker import json_post_checker
import typing as t


async def get_exchanges(req: web.Request) -> web.Response:
    """获取数据中心中所有交易所列表"""
    try:
        async with dc_async_session() as s:
            result = await s.execute(select(Exchange))
            rows = result.all()
        return web.json_response(
            app_response(data=[{"id": r[0].id, "name": r[0].name} for r in rows])
        )
    except Exception as e:
        return web.json_response(
            app_response(code=AppCode.DATA_NOT_READY, msg=str(e))
        )


@json_post_checker(necessary_keys={"name": str})
async def create_exchange(req: web.Request, data: t.Optional[t.Dict[str, t.Any]] = None) -> web.Response:
    """新增交易所"""
    if data is None:
        return web.json_response(
            app_response(code=AppCode.DATA_INVALID, msg="缺少请求体")
        )
    name = data["name"].strip()
    if not name:
        return web.json_response(
            app_response(code=AppCode.DATA_INVALID, msg="交易所名称不能为空")
        )
    try:
        async with dc_async_session() as s:
            existing = await s.execute(select(Exchange).filter_by(name=name))
            if existing.first() is not None:
                return web.json_response(
                    app_response(code=AppCode.DATA_INVALID, msg=f"交易所 '{name}' 已存在")
                )
            s.add(Exchange(name=name))
            await s.commit()
        return web.json_response(app_response(msg=f"交易所 '{name}' 已创建"))
    except Exception as e:
        return web.json_response(
            app_response(code=AppCode.DATA_NOT_READY, msg=str(e))
        )


@json_post_checker(necessary_keys={"name": str})
async def delete_exchange(req: web.Request, data: t.Optional[t.Dict[str, t.Any]] = None) -> web.Response:
    """删除交易所（同时删除该交易所下所有标的）"""
    if data is None:
        return web.json_response(
            app_response(code=AppCode.DATA_INVALID, msg="缺少请求体")
        )
    name = data["name"]
    try:
        async with dc_async_session() as s:
            result = await s.execute(select(Exchange).filter_by(name=name))
            row = result.first()
            if row is None:
                return web.json_response(
                    app_response(code=AppCode.NOT_FOUND, msg=f"交易所 '{name}' 不存在")
                )
            # 级联删除该交易所下的所有标的
            targets = (await s.execute(select(Target).filter_by(exchange=name))).scalars().all()
            for tgt in targets:
                await s.delete(tgt)
            await s.delete(row[0])
            await s.commit()
        return web.json_response(app_response(msg=f"交易所 '{name}' 已删除"))
    except Exception as e:
        return web.json_response(
            app_response(code=AppCode.DATA_NOT_READY, msg=str(e))
        )


async def get_scripts(req: web.Request) -> web.Response:
    """获取数据中心中所有脚本列表"""
    try:
        async with dc_async_session() as s:
            result = await s.execute(select(Script))
            rows = result.all()
        return web.json_response(
            app_response(
                data=[
                    {"id": r[0].id, "name": r[0].name, "content": r[0].content}
                    for r in rows
                ]
            )
        )
    except Exception as e:
        return web.json_response(
            app_response(code=AppCode.DATA_NOT_READY, msg=str(e))
        )


@json_post_checker(necessary_keys={"name": str, "content": str})
async def create_script(req: web.Request, data: t.Optional[t.Dict[str, t.Any]] = None) -> web.Response:
    """新增或更新脚本"""
    if data is None:
        return web.json_response(
            app_response(code=AppCode.DATA_INVALID, msg="缺少请求体")
        )
    try:
        async with dc_async_session() as s:
            existing = await s.execute(select(Script).filter_by(name=data["name"]))
            row = existing.first()
            if row is not None:
                # 更新已有脚本
                row[0].content = data["content"]
            else:
                s.add(Script(name=data["name"], content=data["content"]))
            await s.commit()
        return web.json_response(app_response(msg="脚本已保存"))
    except Exception as e:
        return web.json_response(
            app_response(code=AppCode.DATA_NOT_READY, msg=str(e))
        )


@json_post_checker(necessary_keys={"name": str}, optional_keys={"params": dict})
async def execute_script(req: web.Request, data: t.Optional[t.Dict[str, t.Any]] = None) -> web.Response:
    """加载并执行数据中心脚本"""
    if data is None:
        return web.json_response(
            app_response(code=AppCode.DATA_INVALID, msg="缺少请求体")
        )
    try:
        result = await Script.load_and_execute(
            data["name"], **(data.get("params") or {})
        )
        return web.json_response(app_response(data=result))
    except Exception as e:
        return web.json_response(
            app_response(code=AppCode.EXECUTE_FAILED, msg=str(e))
        )


@json_post_checker(necessary_keys={"name": str})
async def delete_script(req: web.Request, data: t.Optional[t.Dict[str, t.Any]] = None) -> web.Response:
    """删除脚本"""
    if data is None:
        return web.json_response(
            app_response(code=AppCode.DATA_INVALID, msg="缺少请求体")
        )
    name = data["name"]
    try:
        async with dc_async_session() as s:
            result = await s.execute(select(Script).filter_by(name=name))
            row = result.first()
            if row is None:
                return web.json_response(
                    app_response(code=AppCode.NOT_FOUND, msg=f"脚本 '{name}' 不存在")
                )
            await s.delete(row[0])
            await s.commit()
        return web.json_response(app_response(msg=f"脚本 '{name}' 已删除"))
    except Exception as e:
        return web.json_response(
            app_response(code=AppCode.DATA_NOT_READY, msg=str(e))
        )


async def get_targets(req: web.Request) -> web.Response:
    """获取指定交易所下的标的，支持关键字搜索"""
    exchange = req.query.get("exchange", "")
    keyword = req.query.get("keyword", "")
    if not exchange:
        return web.json_response(app_response(data=[]))
    try:
        async with dc_async_session() as s:
            q = select(Target.code).filter_by(exchange=exchange)
            if keyword:
                q = q.filter(Target.code.like(f"%{keyword}%"))
            result = await s.execute(q.limit(50))
            codes = result.scalars().all()
        return web.json_response(app_response(data=list(codes)))
    except Exception as e:
        return web.json_response(app_response(code=AppCode.DATA_NOT_READY, msg=str(e)))


async def check_data_table(req: web.Request) -> web.Response:
    """检查数据表是否存在"""
    exchange = req.query.get("exchange", "")
    code = req.query.get("code", "")
    period_str = req.query.get("period", "3600")
    if not exchange or not code:
        return web.json_response(app_response(code=AppCode.DATA_INVALID, msg="exchange 和 code 不能为空"))
    try:
        period = DataPeriod.from_seconds(int(period_str))
        if period is None:
            return web.json_response(app_response(code=AppCode.DATA_INVALID, msg="无效的周期"))
        target = Target(code=code, exchange=exchange)
        table_name = target.src_table(period)
        async with get_session()() as s:
            result = await s.execute(text(f"select exists(select 1 from information_schema.tables where table_name='{table_name}')"))
            exists = result.fetchone()
        return web.json_response(app_response(data={"table": table_name, "exists": exists[0] if exists is not None else False}))
    except Exception as e:
        return web.json_response(app_response(code=AppCode.DATA_NOT_READY, msg=str(e)))


async def check_data_integrity(req: web.Request) -> web.Response:
    """检查数据表内数据完整性"""
    exchange = req.query.get("exchange", "")
    code = req.query.get("code", "")
    period_str = req.query.get("period", "3600")
    start_str = req.query.get("start", "")
    end_str = req.query.get("end", "")
    if not exchange or not code or not start_str or not end_str:
        return web.json_response(app_response(code=AppCode.DATA_INVALID, msg="参数不完整"))
    try:
        period = DataPeriod.from_seconds(int(period_str))
        if period is None:
            return web.json_response(app_response(code=AppCode.DATA_INVALID, msg="无效的周期"))
        start_ts = int(start_str)
        end_ts = int(end_str)
        # 对齐到周期边界
        period_ms = period.value * 1000
        start_ts = (start_ts // period_ms) * period_ms
        end_ts = (end_ts // period_ms) * period_ms + period_ms - 1
        target = Target(code=code, exchange=exchange)
        table_name = target.src_table(period)

        # 限制最大 100 万条
        expected_count = (end_ts - start_ts) // period_ms + 1
        if expected_count > 1_000_000:
            return web.json_response(app_response(code=AppCode.DATA_INVALID, msg="时间段跨度过大（超过100万条），请缩小范围"))

        async with get_session()() as s:
            # 按 data_type 分组查询数据范围和条数
            query = text(f"""
                SELECT COALESCE(data_type, 0) as data_type, MIN(open_time) as min_time, MAX(open_time) as max_time, COUNT(*) as cnt
                FROM "{table_name}"
                WHERE open_time >= :start_time AND open_time <= :end_time
                GROUP BY data_type
                ORDER BY data_type
            """)
            result = await s.execute(query, {"start_time": start_ts, "end_time": end_ts})
            rows = result.all()

            if not rows:
                return web.json_response(app_response(data={
                    "table": table_name, "query_start": start_ts, "query_end": end_ts,
                    "expected": expected_count, "groups": [],
                }))

            groups = []
            all_complete = True
            for row in rows:
                data_type, min_time, max_time, count = row[0], row[1], row[2], row[3]
                tolerance = period_ms
                complete = count == expected_count and (min_time or 0) - tolerance <= start_ts and (max_time or 0) + tolerance >= end_ts
                if not complete:
                    all_complete = False
                groups.append({
                    "data_type": int(data_type),
                    "count": count,
                    "expected": expected_count,
                    "complete": complete,
                    "min_time": min_time,
                    "max_time": max_time,
                })

            return web.json_response(app_response(data={
                "table": table_name,
                "query_start": start_ts,
                "query_end": end_ts,
                "expected": expected_count,
                "all_complete": all_complete,
                "groups": groups,
            }))
    except Exception as e:
        return web.json_response(app_response(code=AppCode.DATA_NOT_READY, msg=str(e)))


rules = [
    web.route("GET", "/data_center/exchanges", get_exchanges),
    web.route("POST", "/data_center/exchange", create_exchange),
    web.route("POST", "/data_center/exchange/delete", delete_exchange),
    web.route("GET", "/data_center/scripts", get_scripts),
    web.route("GET", "/data_center/targets", get_targets),
    web.route("GET", "/data_center/check_table", check_data_table),
    web.route("GET", "/data_center/check_data", check_data_integrity),
    web.route("POST", "/data_center/script", create_script),
    web.route("POST", "/data_center/script/execute", execute_script),
    web.route("POST", "/data_center/script/delete", delete_script),
]
