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

# =================== DEMO CREDENTIALS (safe) ===================
OANDA_API_KEY = "f0f53a8e9edc5876590a61755f470acd-7b2ca161a8ee8569edcd7fec1487c70b"
OANDA_ACCOUNT_ID = "101-004-35847042-002"
OANDA_ENV = "practice"
TELEGRAM_TOKEN = "8172914158:AAGHyW_q_PrJZpTiNv_X5g0DyfEcgtGykBE"
CHAT_ID = "5372494623"

api = API(access_token=OANDA_API_KEY, environment=OANDA_ENV)

# =================== SAFE SETTINGS FOR $100k ACCOUNT ===================
SYMBOL = "US100_USD"
POSITION_SIZE = 200          # ← FIXED: safe 1% risk per trade
FVG_BUFFER = 0.5
ENTRY_START = "14:30"
ENTRY_END = "15:00"
EXIT_TIME = "15:10"
already_traded_today = False
app = Flask(__name__)

# =================== TELEGRAM + FILE LOG (so you ALWAYS see something) ===================
def log_and_notify(message):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {message}\n"
    with open("bot.log", "a") as f:
        f.write(line)
    # Try Telegram
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      data={"chat_id": CHAT_ID, "text": f"NAS100_BOT\n{message}"}, timeout=10)
    except:
        pass

# =================== PRICE & CANDLES ===================
def get_price():
    try:
        r = instruments.InstrumentsCandles(instrument=SYMBOL, params={"count": 1, "granularity": "M1", "price": "M"})
        api.request(r)
        return round(float(r.response["candles"][0]["mid"]["c"]), 1)
    except:
        return None

def get_candles(count=15, granularity="M15"):
    try:
        r = instruments.InstrumentsCandles(instrument=SYMBOL, params={"count": count, "granularity": granularity, "price": "M"})
        api.request(r)
        return [c for c in r.response["candles"] if c["complete"]]
    except:
        return []

# =================== FVG DETECTION ===================
def detect_fvg():
    candles = get_candles()
    if len(candles) < 3: return None
    c0, c1, c2 = candles[-3], candles[-2], candles[-1]
    h0, l0 = float(c0["mid"]["h"]), float(c0["mid"]["l"])
    h2, l2 = float(c2["mid"]["h"]), float(c2["mid"]["l"])
    if l2 > h0:
        return {"type": "bullish",  "zone_bottom": h0, "zone_top": l2}
    if h2 < l0:
        return {"type": "bearish", "zone_bottom": h2, "zone_top": l0}
    return None

# =================== TRADE & CLOSE ===================
def place_trade(direction, fvg):
    price = get_price()
    if not price: return
    sl = round(price - FVG_BUFFER if direction == "long" else price + FVG_BUFFER, 1)
    tp = round(price + FVG_BUFFER*2 if direction == "long" else price - FVG_BUFFER*2, 1)
    units = POSITION_SIZE if direction == "long" else -POSITION_SIZE

    data = {"order": {
        "instrument": SYMBOL, "units": str(units), "type": "MARKET",
        "timeInForce": "FOK",
        "stopLossOnFill": {"price": str(sl)},
        "takeProfitOnFill": {"price": str(tp)}
    }}
    try:
        r = orders.OrderCreate(OANDA_ACCOUNT_ID, data=data)
        api.request(r)
        log_and_notify(f"FVG {direction.upper()} EXECUTED\nEntry: {price}\nSL {sl} | TP {tp}\nZone {fvg['zone_bottom']}–{fvg['zone_top']}")
    except Exception as e:
        log_and_notify(f"TRADE REJECTED: {str(e)}")

def close_positions():
    try:
        r = accounts.AccountDetails(OANDA_ACCOUNT_ID)
        api.request(r)
        for pos in r.response['account']['positions']:
            if pos['instrument'] == SYMBOL:
                total = float(pos['long']['units']) + float(pos['short']['units'])
                if abs(total) > 50:
                    units = str(int(-total))
                    orders.OrderCreate(OANDA_ACCOUNT_ID, data={"order": {"instrument": SYMBOL, "units": units, "type": "MARKET"}}).request(api)
                    log_and_notify("Position closed")
    except: pass

# =================== MAIN LOOP ===================
def daily_strategy():
    log_and_notify("BOT STARTED – Safe 200-unit size active")
    while True:
        now = datetime.datetime.now()
        t = now.strftime("%H:%M")
        if now.hour == 0 and now.minute < 5:
            global already_traded_today
            already_traded_today = False
            log_and_notify("New day – ready")

        if ENTRY_START <= t <= ENTRY_END and not already_traded_today:
            log_and_notify("Scanning for FVG 14:30–15:00...")
            fvg = detect_fvg()
            if fvg:
                price = get_price() or 0
                low, high = fvg["zone_bottom"], fvg["zone_top"]
                if low - 10 <= price <= high + 10:
                    direction = "long" if fvg["type"] == "bullish" else "short"
                    place_trade(direction, fvg)
                    already_traded_today = True
                else:
                    log_and_notify(f"FVG found but price {price} not in zone yet")
            else:
                log_and_notify("No valid FVG today")

        if t == EXIT_TIME:
            close_positions()

        time.sleep(20)

# =================== LIVE LOG PAGE ===================
@app.route("/")
def home():
    return "<h1>NAS100 FVG Bot LIVE</h1><pre>Check /log for real-time status</pre>"

@app.route("/log")
def log():
    try:
        with open("bot.log", "r") as f:
            return "<pre>" + f.read()[-4000:] + "</pre><meta http-equiv='refresh' content='5'>"
    except:
        return "Log starting..."

if __name__ == "__main__":
    Thread(target=daily_strategy, daemon=True).start()
    log_and_notify("BOT FULLY RUNNING – 200 units | Waiting for 14:30")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))  
    log_and_notify("LOG TEST – Bot is 100% alive right now")
log_and_notify(f"Current time: {datetime.datetime.now().strftime('%H:%M:%S')}")
log_and_notify(f"Position size set to: {POSITION_SIZE} units")
log_and_notify("You will see EVERYTHING here from now on – refresh /log")
log_and_notify("LOG TEST – Bot is 100% alive right now")
log_and_notify(f"Current time: {datetime.datetime.now().strftime('%H:%M:%S')}")
log_and_notify(f"Position size set to: {POSITION_SIZE} units")
log_and_notify("You will see EVERYTHING here from now on – refresh /log")