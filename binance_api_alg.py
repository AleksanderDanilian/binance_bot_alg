import time
import json
import urllib
import hmac, hashlib
import requests
import numpy as np
from statsmodels.tsa.arima_model import ARIMA

from urllib.parse import urlparse, urlencode
from urllib.request import Request, urlopen

class Binance():

    methods = {
            # public methods
            'ping':             {'url':'api/v1/ping', 'method': 'GET', 'private': False},
            'time':             {'url':'api/v1/time', 'method': 'GET', 'private': False},
            'exchangeInfo':     {'url':'api/v1/exchangeInfo', 'method': 'GET', 'private': False},
            'depth':            {'url': 'api/v1/depth', 'method': 'GET', 'private': False},
            'trades':           {'url': 'api/v1/trades', 'method': 'GET', 'private': False},
            'historicalTrades': {'url': 'api/v1/historicalTrades', 'method': 'GET', 'private': False},
            'aggTrades':        {'url': 'api/v1/aggTrades', 'method': 'GET', 'private': False},
            'klines':           {'url': 'api/v1/klines', 'method': 'GET', 'private': False},
            'ticker24hr':       {'url': 'api/v1/ticker/24hr', 'method': 'GET', 'private': False},
            'tickerPrice':      {'url': 'api/v3/ticker/price', 'method': 'GET', 'private': False},
            'tickerBookTicker': {'url': 'api/v3/ticker/bookTicker', 'method': 'GET', 'private': False},
            # private methods
            'createOrder':      {'url': 'api/v3/order', 'method': 'POST', 'private': True},
            'testOrder':        {'url': 'api/v3/order/test', 'method': 'POST', 'private': True},
            'orderInfo':        {'url': 'api/v3/order', 'method': 'GET', 'private': True},
            'cancelOrder':      {'url': 'api/v3/order', 'method': 'DELETE', 'private': True},
            'openOrders':       {'url': 'api/v3/openOrders', 'method': 'GET', 'private': True},
            'allOrders':        {'url': 'api/v3/allOrders', 'method': 'GET', 'private': True},
            'account':          {'url': 'api/v3/account', 'method': 'GET', 'private': True},
            'myTrades':         {'url': 'api/v3/myTrades', 'method': 'GET', 'private': True},
            # wapi
            'depositAddress':   {'url': '/wapi/v3/depositAddress.html', 'method':'GET', 'private':True},
            'withdraw':   {'url': '/wapi/v3/withdraw.html', 'method':'POST', 'private':True},
            'depositHistory': {'url': '/wapi/v3/depositHistory.html', 'method':'GET', 'private':True},
            'withdrawHistory': {'url': '/wapi/v3/withdrawHistory.html', 'method':'GET', 'private':True},
            'withdrawFee': {'url': '/wapi/v3/withdrawFee.html', 'method':'GET', 'private':True},
            'accountStatus': {'url': '/wapi/v3/accountStatus.html', 'method':'GET', 'private':True},
            'systemStatus': {'url': '/wapi/v3/systemStatus.html', 'method':'GET', 'private':True},
    }
    
    
    def __init__(self, API_KEY, API_SECRET):
        self.API_KEY = API_KEY
        self.API_SECRET = bytearray(API_SECRET, encoding='utf-8')
        self.shift_seconds = 0

    def __getattr__(self, name):
        def wrapper(*args, **kwargs):
            kwargs.update(command=name)
            return self.call_api(**kwargs)
        return wrapper

    def set_shift_seconds(self, seconds):
        self.shift_seconds = seconds
        
    def call_api(self, **kwargs):

        command = kwargs.pop('command')
        api_url = 'https://testnet.binance.vision/' + self.methods[command]['url']

        payload = kwargs #словарь
        headers = {}
        
        payload_str = urllib.parse.urlencode(payload)
        if self.methods[command]['private']: # Если стоит ключ private
            payload.update({'timestamp': int(time.time() + self.shift_seconds - 1) * 1000}) #обновляем словарь timestamp
            payload_str = urllib.parse.urlencode(payload).encode('utf-8') # кодируем payload
            sign = hmac.new(
                key=self.API_SECRET,
                msg=payload_str,
                digestmod=hashlib.sha256
            ).hexdigest()
                
            payload_str = payload_str.decode("utf-8") + "&signature="+str(sign) 
            headers = {"X-MBX-APIKEY": self.API_KEY}

        if self.methods[command]['method'] == 'GET':
            api_url += '?' + payload_str

        response = requests.request(method=self.methods[command]['method'], url=api_url, data="" if self.methods[command]['method'] == 'GET' else payload_str, headers=headers)
        if 'code' in response.text:
            print(response.text)
        return response.json()

    def get_signal(self, date_ts=1640998800000, order=(0, 0, 1), symbol="BTCUSDT", interval='1h'):
        trades = np.array(self.klines(symbol=symbol, interval=interval, limit='1000', startTime=date_ts))[:,
                 [1, 4]]  # 4 parameter - close, 1 - open
        trades = trades.astype(float)
        avr_trades = [int((val[0] + val[1]) / 2) for val in trades]  # берем среднее по open/close

        # чтобы сравнивать pred не с реальными данными, а с pred - нужно создать pred[-2].
        avr_trades_1 = avr_trades[:-1]
        avr_trades_2 = avr_trades
        data = [avr_trades_1, avr_trades_2]
        output = []

        for i in range(2):
            model = ARIMA(data[i], order=order)
            model_fit = model.fit()
            output.append(int(model_fit.forecast()[0]))

        # output 1 - реальное предсказание. 
        if output[1] > output[0]:
            signal = 'buy'
        else:
            signal = 'sell'

        return signal