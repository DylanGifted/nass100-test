#!/usr/bin/env python3
"""
Simple OANDA timed bot.

IMPORTANT: This file reads API keys and tokens from environment variables
to avoid committing secrets into the repository. Set `OANDA_API_KEY`,
`OANDA_ACCOUNT_ID`, and `TELEGRAM_TOKEN` in your deployment environment.

This is a lightly refactored version of a script provided by the user.
"""

import os
import requests
import datetime
import time
from threading import Thread
from flask import Flask
from oandapyV20 import API
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.pricing as pricing
import oandapyV20.endpoints.accounts as accounts

# ------------------- CONFIG (read from environment) -------------------
OANDA_API_KEY = os.environ.get("OANDA_API_KEY")
OANDA_ACCOUNT_ID = os.environ.get("OANDA_ACCOUNT_ID")
OANDA_ENV = os.environ.get("OANDA_ENV", "practice")

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

if not OANDA_API_KEY or not OANDA_ACCOUNT_ID:
    raise RuntimeError("OANDA_API_KEY and OANDA_ACCOUNT_ID must be set in the environment")

api = API(access_token=OANDA_API_KEY, environment=OANDA_ENV)

SYMBOL = os.environ.get("SYMBOL", "NAS100_USD")
POSITION_SIZE = int(os.environ.get("POSITION_SIZE", "1000"))
FVG_BUFFER = float(os.environ.get("FVG_BUFFER", "0.5"))
ENTRY_START = os.environ.get("ENTRY_START", "14:30")
ENTRY_END = os.environ.get("ENTRY_END", "15:00")
EXIT_TIME = os.environ.get("EXIT_TIME", "15:10")

already_traded_today = False

app = Flask(__name__)


def send_telegram(message: str) -> None:
    if not TELEGRAM_TOKEN or not CHAT_ID:
        # Not configured, just print
        print("TELEGRAM not configured; message:", message)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, data={"chat_id": CHAT_ID, "text": message}, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print("Failed sending telegram message:", e)


def get_price() -> float:
    r = pricing.PricingInfo(accountID=OANDA_ACCOUNT_ID, params={"instruments": SYMBOL})
    rv = api.request(r)
    # choose ask price
    return float(rv["prices"][0]["closeoutAsk"] if "closeoutAsk" in rv["prices"][0] else rv["prices"][0].get("closeOutAsk") or rv["prices"][0]["asks"][0]["price"]) 


def place_trade(direction: str) -> None:
    entry = get_price()
    sl = round(entry - FVG_BUFFER if direction == "long" else entry + FVG_BUFFER, 1)
    tp = round(entry + FVG_BUFFER * 2 if direction == "long" else entry - FVG_BUFFER * 2, 1)
    units = str(POSITION_SIZE if direction == "long" else -POSITION_SIZE)

    data = {"order": {
        "instrument": SYMBOL,
        "units": units,
        "type": "MARKET",
        "timeInForce": "FOK",
        "stopLossOnFill": {"price": str(sl)},
        "takeProfitOnFill": {"price": str(tp)}
    }}

    r = orders.OrderCreate(OANDA_ACCOUNT_ID, data=data)
    api.request(r)
    send_telegram(f"TRADE {direction.upper()} {SYMBOL}\nEntry ≈ {entry}\nSL {sl} | TP {tp}")


def close_positions() -> None:
    r = accounts.AccountDetails(OANDA_ACCOUNT_ID)
    resp = api.request(r)
    for pos in resp.get('account', {}).get('positions', []):
        if pos.get('instrument') == SYMBOL:
            long_units = float(pos.get('long', {}).get('units', 0))
            short_units = float(pos.get('short', {}).get('units', 0))
            net = long_units + short_units
            if net != 0:
                close_units = -int(net)
                data = {"order": {"instrument": SYMBOL, "units": str(close_units), "type": "MARKET"}}
                r_close = orders.OrderCreate(OANDA_ACCOUNT_ID, data=data)
                api.request(r_close)
                send_telegram("Position closed")


def daily_strategy() -> None:
    global already_traded_today
    while True:
        now = datetime.datetime.now()
        time_str = now.strftime("%H:%M")

        if now.hour == 0 and now.minute == 0:
            already_traded_today = False
            send_telegram("New day – bot ready")

        if ENTRY_START <= time_str <= ENTRY_END and not already_traded_today:
            send_telegram(f"Entry window {time_str} – executing trade")
            # NOTE: replace with your actual signal logic
            place_trade("long")
            already_traded_today = True

        if time_str == EXIT_TIME:
            close_positions()

        time.sleep(15)


@app.route("/")
def home():
    return "OANDA timed bot is alive!"


if __name__ == "__main__":
    send_telegram("Bot successfully deployed")
    Thread(target=daily_strategy, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
