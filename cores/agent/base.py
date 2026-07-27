import typing as t

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.tools import BaseTool, tool
from loguru import logger

from utils.types import SingletonMeta

Model_T: t.TypeAlias = t.Literal['deepseek-v4-pro', '']

class toolMeta(type):
    """
    agent 工具函数管理
    """
    
    ALL: t.ClassVar[list[BaseTool]] = []
    
    def __new__(cls, name: str, bases: tuple[type, ...], namespace: dict[str, t.Any], /, **kwds: t.Any):
        class_meta: type =  type(name, bases, namespace, **kwds)
        if class_meta.__call__.__doc__ == "":
            logger.warning(f'agent tool \'{class_meta.__name__}\' without doc')
        cls.ALL.append(tool(class_meta.__call__))
        
    


class MyAgent(metaclass=SingletonMeta):
    
    def __init__(self, mode: Model_T) -> None:
        self.model = init_chat_model(mode)
        self.agent = create_agent(self.model, tools=toolMeta.ALL)

    
    async def send(self, msg: str):
        pass