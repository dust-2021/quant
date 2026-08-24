import typing as t

from langchain.agents import create_agent
from langchain.tools import BaseTool, tool
from langchain_openai import ChatOpenAI
from loguru import logger

from database.model import Config as ConfDb
from utils.types import SingletonMeta

Model_T: t.TypeAlias = t.Literal["deepseek-v4-pro", "gpt"]

Model_M: t.Mapping[Model_T, type[ChatOpenAI]] = {
    "deepseek-v4-pro": ChatOpenAI,
    "gpt": ChatOpenAI,
}

Tool_T: t.TypeAlias = t.Callable[..., t.Any | t.Awaitable[t.Any]]

class toolManager:
    
    ALL: t.ClassVar[list[BaseTool]] = []
    
    def __init__(self, desc: str = "", perms: list[str] | None = None, **kwargs) -> None:
        self.desc = desc
        self.perms = perms
        self.kwargs = kwargs
        
    def permission_check(self, user_perms: t.Sequence[str]) -> bool:
        if self.perms is None:
            return True
        return any(perm in user_perms for perm in self.perms)
    
    def __call__(self, func: t.Callable[..., t.Any]) -> t.Any:
        
        def wrapper(*args, **kwargs):
            if not self.permission_check(user_perms=[]):  # TODO: 获取用户权限
                logger.warning(f"Permission denied for tool {func.__name__}")
                raise PermissionError(f"Permission denied for tool {func.__name__}")
            return func(*args, **kwargs)
        
        tool_Func = tool(wrapper, description=self.desc if func.__doc__ is None else func.__doc__, **self.kwargs)
        self.ALL.append(tool_Func)
        return tool_Func


class MyAgent(metaclass=SingletonMeta):
    def __init__(self, mode: Model_T) -> None:
        self.model = Model_M.get(mode, ChatOpenAI)(
            model=mode,
            api_key=lambda: ConfDb.get("OpenAIKey"),
            temperature=0.0,
            max_retries=3,
        )
        self.agent = create_agent(self.model, tools=toolManager.ALL)

    async def send(self, msg: str):
        pass
