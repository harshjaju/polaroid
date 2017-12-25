import logging
import time

from apis import Binance

logging.basicConfig(format='%(asctime)s %(message)s', filename='logs.txt', level=logging.DEBUG)
FEES_PERCENT = 0.25
TRADE_VALUE = 0.005
RATE_LIMIT_SLEEP = 30
ORDER_STATUS_WAIT = 3
CYCLE_SLEEP = 20


class Polaroid:
    def __init__(self):
        self.exchange = Binance()

    def _check_validity(self, symbol):
        book = self.exchange.get_order_book(symbol)
        if 'error' in book:
            #TODO Handle this fellow
            raise RuntimeError
        ask = book['asks'][0]['price'] - .000001
        bid = book['bids'][0]['price'] + .000001
        spread = (ask - bid) / ask * 100
        if spread < FEES_PERCENT:
            return False
        return self._mid_profit_rates(ask, bid)

    def _mid_profit_rates(self, ask, bid):
        mid = (ask+bid) / 2
        spread = FEES_PERCENT * ask / 100
        buy = round(mid - (spread/2), 6)
        sell = round(mid + (spread/2), 6)
        return {'bid': buy, 'ask': sell}

    def print_money(self):
        pairs = self._get_profitable_pairs()
        for symbol, lot_size in pairs:
            trade = self._check_validity(symbol)
            if not trade:
                logging.info(f'{symbol} not profitable')
                time.sleep(1)
                continue
            logging.info(f'{symbol} is profitable')
            logging.info(str(trade))
            trade_requests = self.exchange.formulate_requests(symbol, trade, lot_size)
            self._complete_trade(trade_requests['buy'], symbol)
            logging.info('Buy successful. Selling')
            self._complete_trade(trade_requests['sell'], symbol)
            logging.info('Sell successful.')

    def infi(self):
        while True:
            self.print_money()
            logging.info('Cycle complete, sleeping')
            time.sleep(CYCLE_SLEEP)

    def _complete_trade(self, request, symbol):
        order_ok = False
        while not order_ok:
            logging.info(f'making request {request}')
            order = self.exchange.execute_request(request)
            if not order.ok:
                logging.info(f'order not ok. {order.status_code} {order.text}')
                if not self._check_rate_limit(order):
                    # TODO 
                    raise RuntimeError
            order_ok = order.ok
        order_id = order.json()['orderId']
        logging.info(f'order id: {order_id}')
        order_json = order.json()
        logging.info(str(order_json))
        while order_json['status'].lower() != 'filled':
            logging.info(f'querying to see if order {order_id} is filled')
            order = self.exchange.query_order(symbol, order_id)
            if not order.ok:
                logging.info(order.text)
                self._check_rate_limit(order)
                continue
            time.sleep(ORDER_STATUS_WAIT)
            order_json = order.json()
        logging.info(str(order_json))

    def _get_profitable_pairs(self):
        # Hardcoded for now. Will figure out some data driven approach later
        return [('ETHBTC', 3), ('IOTABTC',0), ('DASHBTC', 3), ('XRPBTC',0), ('ADABTC', 0), ('NEOBTC', 2), ('LSKBTC', 2), ('LTCBTC', 2), ('XMRBTC', 3)]

    def _check_rate_limit(self, r):
        if r.status_code == 429:
            logging.info(f'Rate limit hit. Sleeping for {RATE_LIMIT_SLEEP} sec')
            time.sleep(RATE_LIMIT_SLEEP)
            return True
        return False
