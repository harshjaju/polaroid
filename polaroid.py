import logging
import time

from apis import Binance

logging.basicConfig(format='%(asctime)s %(message)s', filename='logs.txt', level=logging.DEBUG)
FEES_PERCENT = 0.3
TRADE_VALUE = 0.005
RATE_LIMIT_SLEEP = 30
ORDER_STATUS_WAIT = 3
CYCLE_SLEEP = 1


class Polaroid:
    def __init__(self, pair):
        self.pair = pair
        self.exchange = Binance()

    def _check_validity(self, symbol):
        book = self.exchange.get_order_book(symbol)
        if 'error' in book:
            #TODO Handle this fellow
            raise RuntimeError
        ask = round(book['asks'][0]['price'] - .000001, 6)
        bid = round(book['bids'][0]['price'] + .000001, 6)
        spread = (ask - bid) / ask * 100
        if spread < FEES_PERCENT:
            return self._mid_profit_rates(ask, bid)
        return {'bid': bid, 'ask': ask}

    def _mid_profit_rates(self, ask, bid):
        mid = (ask+bid) / 2
        spread = FEES_PERCENT * ask / 100
        buy = round(mid - (spread/2), 6)
        sell = round(mid + (spread/2), 6)
        return {'bid': buy, 'ask': sell}

    def print_money(self):
        symbol, lot_size = self.pair
        trade = self._check_validity(symbol)
        logging.info(str(trade))
        trade_requests = self.exchange.formulate_requests(symbol, trade, lot_size)
        with open('trades.txt', 'a') as ttxt:
            ttxt.write(str(time.time()) + '   ')
            ttxt.write(symbol + '\n')
            ttxt.write(str(trade_requests) + '\n')
        self._complete_trade(trade_requests['buy'], symbol)
        with open('trades.txt', 'a') as ttxt:
            ttxt.write(str(time.time()) + '   ')
            ttxt.write(symbol + '\n')
            ttxt.write('Buy successful\n')
        logging.info('Buy successful. Selling')
        self._complete_trade(trade_requests['sell'], symbol)
        logging.info('Sell successful.')
        with open('trades.txt', 'a') as ttxt:
            ttxt.write(str(time.time()) + '   ')
            ttxt.write(symbol + '\n')
            ttxt.write('Sell sucessful\n\n')

    def infi(self):
        while True:
            self.print_money()
            logging.info('Cycle complete, sleeping')
            time.sleep(CYCLE_SLEEP)

    def _complete_trade(self, request, symbol):
        order_ok = False
        # Place order
        while not order_ok:
            logging.info(f'making request {request}')
            order = self.exchange.execute_request(request)
            if not order.ok:
                logging.info(f'order not ok. {order.status_code} {order.text}')
                if not self._check_rate_limit(order):
                    # TODO 
                    with open('trades.txt', 'a') as ttxt:
                        ttxt.write('\n\n\n')
                        ttxt.write(order.text)
                        ttxt.write('\n\n\n')
                    raise RuntimeError
            order_ok = order.ok
        order_id = order.json()['orderId']
        logging.info(f'order id: {order_id}')
        order_json = order.json()
        logging.info(str(order_json))
        # Check if order is filled
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
        return [('ETHBTC', 3), ('XRPBTC',0), ('LTCBTC', 2), ('BCCBTC', 3)]

    def _check_rate_limit(self, r):
        if r.status_code == 429:
            logging.info(f'Rate limit hit. Sleeping for {RATE_LIMIT_SLEEP} sec')
            time.sleep(RATE_LIMIT_SLEEP)
            return True
        return False
