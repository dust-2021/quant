import typing as t


class Binance:
    """"""
    
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        
    
    def _sign(self, data: t.Mapping[str, t.Any], **kwargs: t.Any):
        pass
    
    
    