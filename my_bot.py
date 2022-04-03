import logging
from collections import ChainMap
import time
import os
from pytz import utc
from apscheduler.schedulers.background import BackgroundScheduler

from datetime import datetime

from binance_api_alg import Binance

bot = Binance(
    API_KEY='ruoVDugC5CHZC846qa77I83gl1mTKElRqCsIfhJKiJD93TWnN8Zq1voPJV2mUurd',
    API_SECRET='jdpXb205J4WzKylHCh6QJmUHfpwWWJhkvAXowXJ7zsiwbAGP7kgvU1EWEKkwT2y6'
)

"""
    Пропишите пары, на которые будет идти торговля.
    base - это базовая пара (BTC, ETH,  BNB, USDT) - то, что на бинансе пишется в табличке сверху
    quote - это квотируемая валюта. Например, для торгов по паре NEO/USDT базовая валюта USDT, NEO - квотируемая
    BTCUSDT - signal buy, side buy - покупаем BTC за USDT (base - quote)
"""


def adjust_to_step(value, step, increase=False):
    return ((int(value * 100000000) - int(value * 100000000) % int(
        float(step) * 100000000)) / 100000000) + (float(step) if increase else 0)


class Trade_params:

    base = 'USDT'
    quote = 'BTC'
    symbol = 'BTCUSDT'
    use_stop_loss = False
    stop_loss_val = 10
    buy_lifetime = 180
    use_bnb_fees = True


# Получаем ограничения торгов по всем парам с биржи
local_time = int(time.time())
limits = bot.exchangeInfo()
server_time = int(limits['serverTime']) // 1000

# Подключаем логирование
logging.basicConfig(
    format="%(asctime)s [%(levelname)-5.5s] %(message)s",
    level=logging.DEBUG,
    handlers=[
        logging.FileHandler(
            "{path}/logs/{fname}.log".format(path=os.path.dirname(os.path.abspath(__file__)), fname="binance")),
        # os.path.dirname - весь путь до посл. эл-та. __file__ - это путь к файлу, из которого загружен модуль.
        logging.StreamHandler()
    ])

log = logging.getLogger('')

# Бесконечный цикл программы

shift_seconds = server_time - local_time
bot.set_shift_seconds(shift_seconds)  # Установление смещения времени между сервером и пк

log.debug("""
    Текущее время: {local_time_d} {local_time_u}
    Время сервера: {server_time_d} {server_time_u}
    Разница: {diff:0.8f} {warn}
    Бот будет работать, как будто сейчас: {fake_time_d} {fake_time_u}
""".format(
    local_time_d=datetime.fromtimestamp(local_time), local_time_u=local_time,
    server_time_d=datetime.fromtimestamp(server_time), server_time_u=server_time,
    diff=abs(local_time - server_time),
    warn="ТЕКУЩЕЕ ВРЕМЯ ВЫШЕ" if local_time > server_time else '',
    fake_time_d=datetime.fromtimestamp(local_time + shift_seconds), fake_time_u=local_time + shift_seconds
))


def main():

    last_order = bot.allOrders(symbol = 'BTCUSDT')[-1]
    balance = [{el['asset']:el['free']} for el in bot.account()['balances']]
    balance = dict(ChainMap(*balance))

    ex_info = [el for el in bot.exchangeInfo()['symbols'] if el['symbol'] == 'BTCUSDT']
    step_size = ex_info[0]['filters'][2]['stepSize']
    asset_precision = ex_info[0]['baseAssetPrecision'] # для base и quote величин одинаков

    if last_order['status'] == 'FILLED' and last_order['side'] == 'BUY':
        # предыдущий ордер исполнен и покупали BTC. Смотрим сигнал
        log.info(f'состояние счета - {balance}')
        signal = bot.get_signal()
        log.info(f'{signal}, - ЗНАЧЕНИЕ СИГНАЛА--------------------------')
        # если сигнал к продаже BTC
        if signal == 'sell':
            sell_amount = adjust_to_step(float(balance['BTC']), step_size)
            new_order = bot.createOrder(
                symbol=Trade_params.symbol,
                recvWindow=5000,
                side='SELL',
                type='MARKET',
                quantity="{quantity:0.{precision}f}".format(
                    quantity=sell_amount, precision=asset_precision
                ))
            log.info(f'Создали ордер на продажу BTC {sell_amount}')
            log.info(f'состояние счета - {balance}')

        if signal == 'buy':
            log.info('Получили сигнал к покупке BTC, но он и так куплен')
            log.info(f'состояние счета - {balance}')

    if last_order['status'] == 'FILLED' and last_order['side'] == 'SELL':
        # предыдущий ордер исполнен и продавали BTC (сейчас USDT на руках). Смотрим сигнал
        log.info(f'состояние счета - {balance}')
        signal = bot.get_signal()
        log.info(f'{signal}, - ЗНАЧЕНИЕ СИГНАЛА--------------------------')
        # если сигнал к покупке BTC
        if signal == 'buy':
            curr_rate = float(bot.tickerPrice(symbol=Trade_params.symbol)['price'])
            buy_amount = adjust_to_step(0.95*float(balance['USDT']) / curr_rate, step_size)  # возможно, где то меняется step size
            new_order = bot.createOrder(
                symbol=Trade_params.symbol,
                recvWindow=5000,
                side='BUY',
                type='MARKET',
                quantity="{quantity:0.{precision}f}".format(
                    quantity=buy_amount, precision=asset_precision
                ))
            log.info(f'Создали ордер на покупку BTC {buy_amount}')
            log.info(f'состояние счета - {balance}')

        if signal == 'sell':
            log.info('Получили сигнал к продаже BTC, но он и так продан')
            log.info(f'состояние счета - {balance}')

    if last_order['status'] == 'EXPIRED' or last_order['status'] == 'CANCELLED':
        # если ордер был просрочен или отменен по каким-либо причинам, создаем новый
        log.info('предыдущий ордер был просрочен или отменен')
        log.info(f'состояние счета - {balance}')
        signal = bot.get_signal()
        log.info(f'{signal}, - ЗНАЧЕНИЕ СИГНАЛА--------------------------')

        if last_order['side'] == 'BUY' and signal == 'buy':
            # если мы пытались купить BTC, но не смогли, а сигнал к покупке - то покупаем
            curr_rate = float(bot.tickerPrice(symbol=Trade_params.symbol)['price'])
            buy_amount = adjust_to_step(0.95*float(balance['USDT']) / curr_rate, step_size)  # возможно, где то меняется step size
            new_order = bot.createOrder(
                symbol=Trade_params.symbol,
                recvWindow=5000,
                side='BUY',
                type='MARKET',
                quantity="{quantity:0.{precision}f}".format(
                    quantity=buy_amount, precision=asset_precision
                ))
            log.info(f'Создали ордер на покупку BTC {buy_amount}')
            log.info(f'состояние счета - {balance}')

        if last_order['side'] == 'BUY' and signal == 'sell':
            # пытались купить BTC, но не получилось. А сейчас сигнал к продаже BTC. ЖДЕМ.
            log.info('Получили сигнал к продаже BTC, но он и так продан')
            log.info(f'состояние счета - {balance}')

        if last_order['side'] == 'SELL' and signal == 'sell':
            # если мы пытались продать BTC, но не смогли, а сигнал к продаже - то продаем
            curr_rate = float(bot.tickerPrice(symbol=Trade_params.symbol)['price'])
            sell_amount = adjust_to_step(float(balance['BTC']), step_size)  # возможно, где то меняется step size
            new_order = bot.createOrder(
                symbol=Trade_params.symbol,
                recvWindow=5000,
                side='SELL',
                type='MARKET',
                quantity="{quantity:0.{precision}f}".format(
                    quantity=sell_amount, precision=asset_precision
                ))
            log.info(f'Создали ордер на продажу BTC {sell_amount}')
            log.info(f'состояние счета - {balance}')

        if last_order['side'] == 'SELL' and signal == 'buy':
            # пытались продать BTC, но не получилось. А сейчас сигнал к покупке BTC. ЖДЕМ.
            log.info('Получили сигнал к продаже BTC, но он и так продан')
            log.info(f'состояние счета - {balance}')


if __name__ == '__main__':
    if time.localtime().tm_min < 10:
        scheduler = BackgroundScheduler()
        scheduler.configure(timezone=utc)
        scheduler.add_job(main, 'interval', minutes=60)
        scheduler.start()
        print('Press Ctrl+{0} to exit'.format('Break' if os.name == 'nt' else 'C'))
        try:
            # This is here to simulate application activity (which keeps the main thread alive).
            while True:
                time.sleep(5)
        except (KeyboardInterrupt, SystemExit):
            # Not strictly necessary if daemonic mode is enabled but should be done if possible
            scheduler.shutdown()




