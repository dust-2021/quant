import aiohttp

class Trader:
    
    def __init__(self, api_key: str, base_url: str) -> None:
        raise NotImplementedError("this is an abstract class, please implement it in subclass")
    
    
    async def send_order(self, *args, **kwargs):
        """
        下单接口
        """
        pass
    
    async def get_position(self):
        pass
    
    
    