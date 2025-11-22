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

# =================== CONFIG ===================
OANDA_API_KEY = "f0f53a8e9edc5876590a61755f470acd-7b2ca161a8ee8569edcd7fec1487c70b"
OANDA_ACCOUNT_ID = "101-004-35847042-002"
OANDA_ENV = "practice"
api = API(access_token=OANDA_API_KEY, environment=OANDA_ENV)

TELEGRAM_TOKEN = "8172914158:AAGHyW_q_PrJZpTiNv_X5g0DyfEcgtGykBE"
CHAT_ID = "5372494623"

SYMBOL = "NAS100_USD"
POSITION_SIZE = 1000
FVG_BUFFER = 0.5
ENTRY_START = "14:30"
ENTRY_END = "15:00"
EXIT_TIME = "15:10"

already_traded_today = False
app = Flask(__name__)

def send_telegram(message):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      data={"chat_id": CHAT_ID, "text": message}, timeout=10)
    except:
        pass

# Safe price fetch (never crashes)
def get_price():
    try:
        r = instruments.InstrumentsCandles(instrument=SYMBOL, params={"count": 1, "granularity": "M5"})
        api.request(r)
        price = float(r.response["candles"][0]["mid"]["c"])
        return round(price, 1)
    except:
        return 20000.0

# Get last 10 completed 15-min candles and detect FVG
def detect_fvg():
    try:
        params = {"count": 10, "granularity": "M15", "price": "M"}
        r = instruments.InstrumentsCandles(instrument=SYMBOL, params=params)
        api.request(r)
        candles = [c for c in r.response["candles"] if c["complete"]]
        if len(candles) < 3:
            return None

        c3 = candles[-3]  # 3 candles ago
        c2 = candles[-2]
        c1 = candles[-1]

        high3 = float(c3["mid"]["h"])
        low3  = float(c3["mid"]["l"])
        high1 = float(c1["mid"]["h"])
        low1  = float(c1["mid"]["l"])

        # Bullish FVG: gap between low of c1 and high of c3
        if low1 > high3:
            return {"type": "bullish", "zone_top": low1, "zone_bottom": high3}
        # Bearish FVG: gap between high of c1 and low of c3
        if high1 < low3:
            return {"type": "bearish", "zone_top": low3, "zone_bottom": high1}
    except:
        pass
    return None

def place_trade(direction, fvg_zone=None):
    entry = get_price()
    sl = round(entry - FVG_BUFFER if direction == "long" else entry + FVG_BUFFER, 1)
    tp = round(entry + FVG_BUFFER*2 if direction == "long" else entry - FVG_BUFFER*2, 1)
    units = POSITION_SIZE if direction == "long" else -POSITION_SIZE

    data = {"order": {
        "instrument": SYMBOL,
        "units": str(units),
        "type": "MARKET",
        "timeInForce": "FOK",
        "stopLossOnFill": {"price": str(sl)},
        "takeProfitOnFill": {"price": str(tp)}
    }}
    r = orders.OrderCreate(OANDA_ACCOUNT_ID, data=data)
    try:
        api.request(r)
        msg = f"FVG {direction.upper()} EXECUTED\nEntry ≈ {entry}\nSL {sl} | TP {tp}"
        if fvg_zone:
            msg += f"\nFVG Zone: {fvg_zone['zone_bottom']} – {fvg_zone['zone_top']}"
        send_telegram(msg)
    except Exception as e:
        send_telegram(f"Trade failed: {str(e)}")

def close_positions():
    try:
        r = accounts.AccountDetails(OANDA_ACCOUNT_ID)
        api.request(r)
        for pos in r.response['account']['positions']:
            if pos['instrument'] == SYMBOL:
                units = pos['long']['units']
                short = pos['short']['units']
                total = float(units) + float(short)
                if abs(total) > 0:
                    close_units = int(-total)
                    data = {"order": {"instrument": SYMBOL, "units": str(close_units), "type": "MARKET"}}
                    orders.OrderCreate(OANDA_ACCOUNT_ID, data=data).request(api)
                    send_telegram(f"Position closed at {datetime.datetime.now().strftime('%H:%M')}")
    except:
        pass

def daily_strategy():
    global already_traded_today
    while True:
        now = datetime.datetime.now()
        t = now.strftime("%H:%M")

        # Daily reset
        if now.hour == 0 and now.minute < 5:
            already_traded_today = False
            send_telegram("New day – FVG bot ready")

        # Entry window
        if ENTRY_START <= t <= ENTRY_END and not already_traded_today:
            send_telegram("Scanning for FVG in 14:30–15:00 window...")
            fvg = detect_fvg()
            if fvg:
                direction = "long" if fvg["type"] == "bullish" else "short"
                place_trade(direction, fvg)
                already_traded_today = True
            else:
                send_telegram("No valid FVG found – skipping today")

        # Force exit
        if t == EXIT_TIME:
            close_positions()

        time.sleep(20)

@app.route("/")
def home():
    return "OANDA FVG Bot v2 – Running & Scanning 15min FVGs!"

if __name__ == "__main__":
    send_telegram("OANDA FVG BOT v2 STARTED – Real 15min FVG Detection Active!")
    Thread(target=daily_strategy, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)