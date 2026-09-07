import os

BASE_PATH = os.getcwd()

class Config:
    """
    配置默认值，当db中未存有时使用
    """
    Port = 5000
    Living = False
    BaseLog = 'INFO'
    WebLog = 'INFO'
    SQLAlchemyLog = "WARNING"
    Auth = False
    DataCenterLink = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/data_center"
    MainDbLink = ""
    MaxHttpPayload = 50 * 1024 * 1024 # 50M
    
    # === 交易所配置（启动时自动初始化到 exchange 表）===
    Exchanges = ["binance"]
    
    # === 缓存配置（可选，RedisHost 留空时使用 diskcache）===
    RedisHost = "127.0.0.1"
    RedisPort = 6379
    RedisPassword = ""
    RedisDb = 0
    
    # === Celery 配置 ===
    CeleryBroker = "amqp://guest:guest@127.0.0.1:5672//"
    CeleryBackend = "redis://127.0.0.1:6379/1"
    
    # === 动态配置 ===
    
    AvailableProxy = False
    ProxyAddress = ""
    ProxyPort = 0
    KlineCount = 1000  # 实盘K线数量（最大1500）
    
    Model = ""
    ApiKey = ""
    AgentPrompt = "你是一个量化回测工具系统的助手"
    