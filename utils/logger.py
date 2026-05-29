import inspect
import logging
from loguru import logger


class InterceptHandler(logging.Handler):
    """将标准 logging 拦截并转发到 loguru"""

    def emit(self, record: logging.LogRecord) -> None:
        # 获取对应的 loguru 级别
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # 获取原始调用栈信息
        stack = inspect.stack()
        # 找到原始日志调用的位置
        for frame in stack:
            if frame.function != 'emit' and not frame.filename.endswith('logging/__init__.py'):
                # 计算相对于当前位置的栈层级
                stacklevel = len(stack) - stack.index(frame)
                break
        else:
            # 如果没有找到，使用默认值
            stacklevel = 3

        logger.opt(depth=stacklevel, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging(
    level: str = "INFO",
    sqlalchemy_level: str = "INFO",
    aiohttp_level: str = "INFO",
) -> None:
    """
    统一日志配置：将 aiohttp / SQLAlchemy 日志接管到 loguru

    Args:
        level: 全局默认日志级别
        sqlalchemy_level: SQLAlchemy 日志级别（建议 WARNING，避免 ROLLBACK 噪音）
        aiohttp_level: aiohttp 日志级别
    """
    # 1. 移除 loguru 默认 handler，重新配置
    logger.remove()
    logger.add(
        sink=__import__("sys").stderr,
        level=level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # 2. 拦截所有标准 logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # 3. 单独控制 SQLAlchemy 各模块级别
    for name in [
        "sqlalchemy",
        "sqlalchemy.engine",
        "sqlalchemy.engine.Engine",
        "sqlalchemy.pool",
        "sqlalchemy.dialects",
        "sqlalchemy.orm",
    ]:
        logging.getLogger(name).setLevel(sqlalchemy_level)
        logging.getLogger(name).handlers = [InterceptHandler()]
        logging.getLogger(name).propagate = False

    # 4. 单独控制 aiohttp 各模块级别
    for name in [
        "aiohttp",
        "aiohttp.access",
        "aiohttp.client",
        "aiohttp.internal",
        "aiohttp.server",
        "aiohttp.web",
    ]:
        logging.getLogger(name).setLevel(aiohttp_level)
        logging.getLogger(name).handlers = [InterceptHandler()]
        logging.getLogger(name).propagate = False
