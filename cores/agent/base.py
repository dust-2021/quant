from langchain.agents import create_agent
from langchain.tools import tool, BaseTool
from utils.types import SingletonMeta
import typing as t
import asyncio
from loguru import logger
from database.model import Config

model_T: t.TypeAlias = t.Literal['deepseek-v4-pro', '']

class toolMeta(type):
    """
    agent 工具函数管理
    """
    
    ALL: t.List[BaseTool] = []
    
    def __new__(cls, name: str, bases: tuple[type, ...], namespace: dict[str, t.Any], /, **kwds: t.Any):
        class_meta: type =  type(name, bases, namespace, **kwds)
        if class_meta.__call__.__doc__ == "":
            logger.warning(f'agent tool \'{class_meta.__name__}\' without doc')
        cls.ALL.append(tool(class_meta.__call__))
        
    


class MyAgent(metaclass=SingletonMeta):
    """"""
    
    def __init__(self, mode: model_T = asyncio.run(Config.get(""))) -> None:
        self.agent = create_agent(mode, tools=[])

    
    def send(self, msg: str):
        pass