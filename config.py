import os
from enum import Enum

BASE_PATH = os.getcwd()

class Config(Enum):
    """
    配置存储关键字，所有配置存于数据库的名称
    """
    Port = 5000
    BaseLog = 'INFO'
    WebLog = 'INFO'
    SQLAlchemyLog = "WARNING"
    Auth = False
    
    # === 动态配置 ===
    
    AvailableProxy = False
    ProxyAddress = ""
    ProxyPort = 0
    
    DataCenter = ""