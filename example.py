import time
from catalyst import run_algorithm
from catalyst.utils_quadency.logger import Logger
from catalyst.api import symbol, set_benchmark, order, cancel_order, can_order_amount
from catalyst.utils_quadency.streams.event import QuadEvent
from catalyst.utils_quadency.quad_api_client import get_latest_price
from catalyst.utils_quadency.streams.helpers import update_book, set_book_snapshot, get_best_bid_ask

ALGO_INPUTS = {
    "EXCHANGE": "binance",  # exchange must be lowercase
    "PAIR": "btc_usdt",  # pair (market) must be lowercase (snake case)
    "ORDER_AMOUNT": 0.01,  # amount to order (in this example we place a limit order to buy 0.01 BTC at 1000 = $10, and cancel the order upon confirmation
    "ORDER_PRICE": 1000,  # price to buy for this example
}

log = Logger()


def initialize(context):
    context.NORMALIZED_PAIR = ALGO_INPUTS["PAIR"].upper().replace("_", "/")
    log.info(f'Initializing algo: {context.NORMALIZED_PAIR} @ {ALGO_INPUTS["EXCHANGE"]}')
    context.SYMBOL = symbol(symbol_str=ALGO_INPUTS["PAIR"], exchange_name=ALGO_INPUTS["EXCHANGE"])
    set_benchmark(context.SYMBOL)
    context.EXITED = False
    context.PLACING_ORDERS = False
    context.CANCELLING_ORDERS = False


def initialize_handle_events(context):
    # Called upon successful subscription to websocket streams.
    # This function can be used to initialize anything that depends on data from streams

    # log out last price for symbol
    last_price = get_latest_price(ALGO_INPUTS["EXCHANGE"], ALGO_INPUTS["PAIR"])
    log.info(f"Last price for {ALGO_INPUTS['PAIR']} is {last_price}")

    # place order to buy
    if not context.PLACING_ORDERS:
        place_order(context)


# handle events from websocket streams here (public and private)
def handle_events(context, event):
    # prevent further processing if algo has been stopped
    if context.EXITED:
        return

    # following 2 events are related to order book updates
    if event.event_type == QuadEvent.ORDER_BOOK_SNAPSHOT:
        set_book_snapshot(event.event_attributes)
    if event.event_type == QuadEvent.ORDER_BOOK_DELTA:
        update_book(event.event_attributes)
        # uncomment the following 2 lines to output best bid/ask
        # best_bid_ask = get_best_bid_ask()
        # log.info(f"Best bid/ask: {best_bid_ask}")

    # hook logic to react to order events for the account here (order cancellations, and fills are notified here)
    if event.event_type == QuadEvent.USER_ORDER:
        log.info(f"Order update received: {event.event_attributes}")
        open_orders = context.blotter.open_orders[context.SYMBOL]
        if len(open_orders) > 0 and not context.CANCELLING_ORDERS:
            cancel_all_orders(context)

    if event.event_type == QuadEvent.SCHEDULE:
        log.info(f"Schedule event fired")


def validate_balances(context):
    current_balance = context.blotter.exchanges[ALGO_INPUTS["EXCHANGE"]].get_balances()
    quote_balance = current_balance[context.SYMBOL.quote_currency]["free"]

    order_total = ALGO_INPUTS["ORDER_AMOUNT"] * ALGO_INPUTS["ORDER_PRICE"]
    if quote_balance < order_total:
        log.error(
            f"Current {context.SYMBOL.quote_currency.upper()} balance is {quote_balance}. Need at least {order_total} "
            f"to place buy order")
        return False
    return True


def place_order(context):
    if context.PLACING_ORDERS:
        return

    context.PLACING_ORDERS = True

    if validate_balances(context):
        try:
            order_id = order(
                asset=context.SYMBOL,
                amount=ALGO_INPUTS["ORDER_AMOUNT"],
                limit_price=ALGO_INPUTS["ORDER_PRICE"]
            )
            log.info(f"Placed order of {ALGO_INPUTS['ORDER_AMOUNT']}@{ALGO_INPUTS['ORDER_AMOUNT']}, order id is {order_id}")
            context.PLACING_ORDERS = False
        except Exception as e:
            log.info(f"Failed to place order because: {e}")
            finalize(context)


def cancel_all_orders(context):
    # only orders placed/managed by the algo are cancelled
    orders = context.blotter.open_orders[context.SYMBOL]
    for o in orders:
        log.info(f"Cancelling order: {o.id}")
        try:
            cancel_order(o, context.SYMBOL)
        except Exception as e:
            log.info(f"Failed to cancel order because: {e}")
            finalize(context)


def finalize(context):
    if not context.EXITED:
        context.EXITED = True
        log.info("Stopping bot")
        context.interrupt_algorithm()


def pre_init():
    # set or calculate starting capital for this algo. Starting capital is required and used to report performance of the algo.
    ALGO_INPUTS["STARTING_CAPITAL"] = ALGO_INPUTS["ORDER_AMOUNT"] * ALGO_INPUTS["ORDER_PRICE"]


pre_init()
