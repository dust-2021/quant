import os

BASE_PATH = os.getcwd()

class Config:
    """
    配置默认值，当db中未存有时使用
    """
    Port = 5000
    BaseLog = 'INFO'
    WebLog = 'INFO'
    SQLAlchemyLog = "WARNING"
    Auth = False
    DataCenterLink = "postgresql+asyncpg://postgres:064735@127.0.0.1:5432/data_center"
    MaxHttpPayload = 50 * 1024 * 1024 # 50M
    
    # === 动态配置 ===
    
    AvailableProxy = False
    ProxyAddress = ""
    ProxyPort = 0
    
    Exchange = ""
    
    Model = ""
    ApiKey = ""
    AgentPrompt = "你是一个量化工具系统的助手"
    