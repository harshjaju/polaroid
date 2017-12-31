import datetime
import logging
import time

from apis import Binance

logging.basicConfig(format='%(asctime)s %(message)s', filename='logs.txt', level=logging.DEBUG)
FEES_PERCENT = 0.3
RATE_LIMIT_SLEEP = 30
ORDER_STATUS_WAIT = 3
CYCLE_SLEEP = 1
SQUARE_OFF_PERCENT = 5


class Polaroid:
    def __init__(self, pair, trade_value):
        self.symbol, self.lot_size = pair
        self.trade_value = trade_value
        self.exchange = Binance()
        self.trade = {}
        self.round_off = 8 if self.symbol == 'XRPBTC' else 6

    def _get_trade_rate(self):
        book = self.exchange.get_order_book(self.symbol)
        if 'error' in book:
            #TODO Handle this fellow
            raise RuntimeError(book['error'])
        ask = round(book['asks'][0]['price'], self.round_off)
        bid = round(book['bids'][0]['price'], self.round_off)
        mid = (ask + bid) / 2
        spread = (ask - bid) / ask * 100
        if spread < FEES_PERCENT:
            return self._mid_profit_rates(ask, bid)
        return {'bid': bid, 'ask': ask, 'mid': mid}

    def _mid_profit_rates(self, ask, bid):
        mid = (ask+bid) / 2
        spread = FEES_PERCENT * ask / 100
        buy = round(mid - (spread/2), self.round_off)
        sell = round(mid + (spread/2), self.round_off)
        return {'bid': buy, 'ask': sell, 'mid': mid}

    def print_money(self):
        self.trade = self._get_trade_rate()
        self._aggressive_buy()
        self._sell()

    def _aggressive_buy(self):
        req = self._formulate_buy_request()
        order_id = self._place_order(req)
        while True:
            # Check if filled
            time.sleep(ORDER_STATUS_WAIT)
            logging.info(f'{self.symbol} querying to see if order {order_id} is filled')
            order = self.exchange.query_order(self.symbol, order_id)
            if not order.ok:
                logging.info(order.text)
                if self._check_rate_limit(order):
                    continue
                else:
                    raise RuntimeError(order.text)
            order_json = order.json()
            if order_json.get('status').lower() == 'filled':
                # Order has been executed
                with open(f'{self.symbol}_trades.txt', 'a') as ttxt:
                    ttxt.write(f'{str(datetime.datetime.now())} : BUY {self.trade["bid"]} successful\n')
                break
            print(f'{self.trade["mid"]} trades mid')
            if float(order_json.get('executedQty', '0')) > 0:
                # Order is partially filled, leave it
                continue
            # See if the mid has increased, in which case, delete order, and place new one
            rates = self._get_trade_rate()
            print(f'{rates["mid"]} rates mid')
            if rates['mid'] > self.trade['mid']:
                self.trade = rates
                print(f'deleting {order_id}')
                r = self.exchange.delete_order(self.symbol, order_id)
                if not r.ok:
                    print(r.text)
                    continue
                self._aggressive_buy()
                break

    def _sell(self):
        req = self._formulate_sell_request()
        order_id = self._place_order(req)
        order_json = {'status' : 'new'}
        while order_json['status'].lower() != 'filled':
            time.sleep(ORDER_STATUS_WAIT)
            logging.info(f'{self.symbol} querying to see if order {order_id} is filled')
            order = self.exchange.query_order(self.symbol, order_id)
            if not order.ok:
                logging.info(order.text)
                self._check_rate_limit(order)
                continue
            order_json = order.json()
            rates = self._get_trade_rate()
            # square off if price has dropped by SQUARE_OFF_PERCENT
            if (self.trade['mid'] - rates['mid']) / self.trade['mid'] * 100 > SQUARE_OFF_PERCENT:
                self.exchange.delete_order(self.symbol, order_id)
                self._square_off()
                break
        else:
        # Order has been executed
            with open(f'{self.symbol}_trades.txt', 'a') as ttxt:
                ttxt.write(f'{str(datetime.datetime.now())} : SELL {self.trade["ask"]} successful\n')

    def _square_off(self):
        req = self._formulate_sell_request(square_off=True)
        order_id = self._place_order(req)
        order_json = {'status' : 'new'}
        while order_json['status'].lower() != 'filled':
            time.sleep(ORDER_STATUS_WAIT)
            logging.info(f'{self.symbol} querying to see if order {order_id} is filled')
            order = self.exchange.query_order(self.symbol, order_id)
            if not order.ok:
                logging.info(order.text)
                self._check_rate_limit(order)
                continue
            order_json = order.json()
        # Order has been executed
        with open(f'{self.symbol}_trades.txt', 'a') as ttxt:
            ttxt.write(f'{str(datetime.datetime.now())} : SQUARE_OFF {self.trade["bid"]} successful\n')

    def infi(self):
        while True:
            self.print_money()
            logging.info('Cycle complete, sleeping')
            time.sleep(CYCLE_SLEEP)

    def _place_order(self, request):
        print(f'Requesting: {request}')
        logging.info(request)
        order_ok = False
        # Place order
        while not order_ok:
            logging.info(f'making request {request}')
            order = self.exchange.execute_request(request)
            if not order.ok:
                logging.info(f'order not ok. {order.status_code} {order.text}')
                if not self._check_rate_limit(order):
                    # TODO 
                    with open(f'{self.symbol}_trades.txt', 'a') as ttxt:
                        ttxt.write('\n\n\n')
                        ttxt.write(order.text)
                        ttxt.write('\n\n\n')
                    raise RuntimeError(order.text)
            order_ok = order.ok
        return order.json()['orderId']

    def _get_profitable_pairs(self):
        # Hardcoded for now. Will figure out some data driven approach later
        return [('ETHBTC', 3), ('XRPBTC',0), ('LTCBTC', 2), ('BCCBTC', 3)]

    def _check_rate_limit(self, r):
        if r.status_code == 429:
            logging.info(f'Rate limit hit. Sleeping for {RATE_LIMIT_SLEEP} sec')
            time.sleep(RATE_LIMIT_SLEEP)
            return True
        return False

    def _format_rates(self):
        if type(self.trade['ask']) is not str:
            self.trade['ask'] = format(self.trade['ask'], '.8f')
            self.trade['bid'] = format(self.trade['bid'], '.8f')

    def _formulate_buy_request(self):
        self._format_rates()
        quantity = round(self.trade_value / float(self.trade['ask']), self.lot_size)
        return f'symbol={self.symbol}&side=BUY&type=LIMIT&timeInForce=GTC&quantity={quantity}&price={self.trade["bid"]}'

    def _formulate_sell_request(self, square_off=False):
        self._format_rates()
        quantity = round(self.trade_value / float(self.trade['ask']), self.lot_size)
        price = self.trade['bid'] if square_off else self.trade['ask']
        return f'symbol={self.symbol}&side=SELL&type=LIMIT&timeInForce=GTC&quantity={quantity}&price={price}'

