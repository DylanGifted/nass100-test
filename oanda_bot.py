import os
import requests
import datetime
import time
from threading import Thread
from flask import Flask
from oandapyV20 import API
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.instruments as instruments
import oandapyV20.endpoints.accounts as accounts

# =================== CONFIG (ENV VARS) ===================
OANDA_API_KEY = os.environ.get("OANDA_API_KEY")
OANDA_ACCOUNT_ID = os.environ.get("OANDA_ACCOUNT_ID")
OANDA_ENV = os.environ.get("OANDA_ENV", "practice")  # "practice" or "live"
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# Safety check
required = ["OANDA_API_KEY", "OANDA_ACCOUNT_ID", "TELEGRAM_TOKEN", "CHAT_ID"]
missing = [v for v in required if not os.environ.get(v)]
if missing:
    raise EnvironmentError(f"Missing env variables: {', '.join(missing)}")

api = API(access_token=OANDA_API_KEY, environment=OANDA_ENV)

SYMBOL = "US100_USD"          # Correct OANDA symbol
POSITION_SIZE = 1000
FVG_BUFFER = 0.5
ENTRY_START = "14:30"
ENTRY_END = "15:00"
EXIT_TIME = "15:10"
already_traded_today = False

app = Flask(__name__)

# =================== TELEGRAM ===================
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        r = requests.post(url, data=payload, timeout=10)
        if r.status_code != 200:
            print(f"Telegram Error {r.status_code}: {r.text}")
    except Exception as e:
        print(f"Telegram Exception: {e}")

# =================== PRICE & CANDLES ===================
def get_price():
    try:
        params = {"count": 2, "granularity": "M1", "price": "M"}
        r = instruments.InstrumentsCandles(instrument=SYMBOL, params=params)
        api.request(r)
        return round(float(r.response["candles"][-1]["mid"]["c"]), 1)
    except:
        return None

def get_candles(count=20, granularity="M15"):
    try:
        params = {"count": count, "granularity":ulate": granularity, "price": "M"}
        r = instruments.InstrumentsCandles(instrument=SYMBOL, params=params)
        api.request(r)
        return [c for c in r.response["candles"] if c["complete"]]
    except:
        return []

# =================== FVG DETECTION (Strict & Accurate) ===================
def detect_fvg():
    candles = get_candles(count=10, granularity="M15")
    if len(candles) < 3:
        return None

    c0 = candles[-3]  # oldest
    c1 = candles[-2]  # middle
    c2 = candles[-1]  # newest

    high0 = float(c0["mid"]["h"])
    low0  = float(c0["mid"]["l"])
    high2 = float(c2["mid"]["h"])
    low2  = float(c2["mid"]["l"])

    # Bullish FVG: gap up (middle candle completely above the first)
    if low2 > high0:
        return {
            "type": "bullish",
            "zone_bottom": high0,
            "zone_top": low2
        }
    # Bearish FVG: gap down
    if high2 < low0:
        return {
            "type": "bearish",
            "zone_bottom": high2,
            "zone_top": low0
        }
    return None

# =================== TRADE EXECUTION ===================
def place_trade(direction, fvg):
    price = get_price()
    if not price:
        send_telegram("Failed to get price – trade skipped")
        return

    sl = round(price - FVG_BUFFER if direction == "long" else price + FVG_BUFFER, 1)
    tp = round(price + FVG_BUFFER*2 if direction == "long" else price - FVG_BUFFER*2, 1)
    units = POSITION_SIZE if direction == "long" else -POSITION_SIZE

    data = {
        "order": {
            "instrument": SYMBOL,
            "units": str(units),
            "type": "MARKET",
            "timeInForce": "FOK",
            "stopLossOnFill": {"price": str(sl)},
            "takeProfitOnFill": {"price": str(tp)}
        }
    }

    r = orders.OrderCreate(OANDA_ACCOUNT_ID, data=data)
    try:
        api.request(r)
        msg = (f"FVG {direction.upper()} EXECUTED\n"
               f"Entry ≈ {price}\n"
               f"SL: {sl} | TP: {tp}\n"
               f"FVG Zone: {fvg['zone_bottom']} – {fvg['zone_top']}\n"
               f"Time: {datetime.datetime.now().strftime('%H:%M')}")
        send_telegram(msg)
    except Exception as e:
        send_telegram(f"Trade FAILED: {str(e)}")

def close_positions():
    try:
        r = accounts.AccountDetails(OANDA_ACCOUNT_ID)
        api.request(r)
        for pos in r.response['account']['positions']:
            if pos['instrument'] == SYMBOL:
                units_long = float(pos['long']['units'])
                units_short = float(pos['short']['units'])
                total = units_long + units_short
                if abs(total) > 50:  # avoid noise
                    close_units = int(-total)
                    data = {"order": {"instrument": SYMBOL, "units": str(close_units), "type": "MARKET"}}
                    orders.OrderCreate(OANDA_ACCOUNT_ID, data=data).request(api)
                    send_telegram(f"Position closed at {datetime.datetime.now().strftime('%H:%M')}")
    except Exception as e:
        send