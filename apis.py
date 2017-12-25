import hashlib
import hmac
import time

import requests

from credentials import binance

class Binance:
    def __init__(self):
        self.secret = binance['secret']
        self.api_key = binance['api_key']
        self.api_root = binance['api_root']

    def get_order_book(self, symbol, depth=10):
        r = requests.get(f'{self.api_root}/api/v1/depth', params={'symbol':symbol, 'limit': 5})
        if not r.ok:
            return {'error': r}
        order_book = r.json()
        bids = [{'price': float(bid[0]), 'quantity': float(bid[1])} for bid in order_book['bids'][:depth]]
        asks = [{'price': float(ask[0]), 'quantity': float(ask[1])} for ask in order_book['asks'][:depth]]
        return {'bids': bids, 'asks': asks}

    def formulate_requests(self, symbol, trades, lot_size, value=0.005):
        quantity = round(value / trades['ask'], lot_size)
        buy = f'symbol={symbol}&side=BUY&type=LIMIT&timeInForce=GTC&quantity={quantity}&price={trades["bid"]}'
        sell = f'symbol={symbol}&side=SELL&type=LIMIT&timeInForce=GTC&quantity={quantity}&price={trades["ask"]}'
        return {'buy': buy, 'sell': sell}

    def execute_request(self, request, action='post'):
        message = f'{request}&timestamp={str(int(time.time() * 1000))}'
        message_bytes = bytes(message, 'utf-8')
        secret = bytes(self.secret, 'utf-8')
        signature = hmac.new(secret, msg=message_bytes, digestmod=hashlib.sha256).hexdigest()
        if action == 'post':
            req = requests.post
        elif action == 'get':
            req = requests.get
        r = req(f'{self.api_root}/api/v3/order', 
                params=f'{message}&signature={signature}',
                headers={'X-MBX-APIKEY': self.api_key})
        return r

    def query_order(self, symbol, order_id):
        request = f'symbol={symbol}&orderId={order_id}'
        r = self.execute_request(request, action='get')
        return r