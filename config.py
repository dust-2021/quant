import os

BASE_PATH = os.getcwd()

class Config:
    """
    配置存储关键字，所有配置存于数据库的名称
    """
    Port = 5000
    BaseLog = 'INFO'
    WebLog = 'INFO'
    SQLAlchemyLog = "WARNING"
    Auth = False
    DataCenterLink = "postgresql+asyncpg://postgres:064735@127.0.0.1:5432/data_center"
    
    # === 动态配置 ===
    
    AvailableProxy = False
    ProxyAddress = ""
    ProxyPort = 0
    
    Exchange = ""
    