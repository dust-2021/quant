import base64
import hashlib
import hmac
import time
import typing as t


class Binance:

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def _sign(self, msg: str):
        h = hmac.new(
            self.api_key.encode(), msg.encode(), digestmod=hashlib.sha256
        ).digest()
        return base64.b64encode(h).decode().lower()

    def _formatter(self, data: dict[str, t.Any], sign: bool = False) -> str:
        if sign and self.api_key == '':
            raise ValueError('binance without api key')
        if len(data) == 0:
            return ""
        if sign:
            data['recvWindow'] = 5000
            data['timestamp'] = int(time.time()) * 1000
        query = '&'.join([f'{k}={v}' for k, v in data])
        if not sign:
            return f'?{query}'
        return f"?{query}&signature={self._sign(query)}"
        

    async def request(
        self,
        url: str,
        method: t.Literal["GET", "POST"] = "GET",
        data: t.Mapping[str, t.Any] | None = None,
        sign: bool = False,
    ):
        pass

    def trade(
        self,
    ):
        pass
