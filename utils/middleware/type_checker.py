import typing as t
from aiohttp import web
from functools import wraps
from utils.types import app_response, AppCode

def json_post_checker(necessary_keys: t.Mapping[str, type], optional_keys: t.Optional[t.Mapping[str, type]] = None):
    """
    接口参数类型和传入检测
    Example:
    @json_post_checker({"name": str, "age": int})
    async def view(req: web.Request, data: dict = None) -> web.Response:
        return web.response()
        
    json解析完成并以关键字传参传入函数
    :param necessary_keys: 必传参数名和类型
    :param optional_keys: 可选参数名和类型
    :param encrypted: 是否为rsa加密传输，https不加密
    :return:
    """

    def decorator(func: t.Callable[[web.Request, t.Optional[t.Dict[str, t.Any]]], t.Awaitable[web.Response]]) -> t.Callable[[web.Request], t.Awaitable[web.Response]]:
        @wraps(func)
        async def wrapper(req: web.Request) -> web.Response:
            # 非post跳过检测
            if req.method != "POST":
                return await func(req, None)
            if req.headers.get("Content-Type") != "application/json":
                return web.json_response(app_response(code=AppCode.DATA_INVALID, msg="仅支持JSON格式"))
            
            data = await req.json()

            # 检测必传参数类型
            for key in necessary_keys:
                if (item := data.get(key)) is None:
                    return web.json_response(app_response(code=AppCode.DATA_INVALID, msg=f"缺失值：{key}"))
                if not isinstance(item, necessary_keys[key]):
                    return web.json_response(app_response(code=AppCode.DATA_INVALID,
                                         msg=f"类型错误--\"{key}\" 期望类型：'{necessary_keys[key].__name__}'，实际类型：'" \
                                             f"{item.__class__.__name__}'"))
            # 检测可选参数类型
            if optional_keys is not None:
                for key in optional_keys:
                    if (item := data.get(key)) is None:
                        continue

                    if not isinstance(item, optional_keys[key]):
                        return web.json_response(app_response(code=AppCode.DATA_INVALID,
                                             msg=f"类型错误--\"{key}\" 期望类型：'{optional_keys[key].__name__}'，实际类型：'" \
                                                 f"{item.__class__.__name__}'"))
            return await func(req, data)

        return wrapper

    return decorator

