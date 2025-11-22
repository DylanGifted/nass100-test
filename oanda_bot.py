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

# =================== HARD-CODED FOR DEMO (safe to share) ===================
OANDA_API_KEY = "f0f53a8e9edc5876590a61755f470acd-7b2ca161a8ee8569edcd7fec1487c70b"  # your old one (still works on practice)
OANDA_ACCOUNT_ID = "101-004-35847042-002"
OANDA_ENV = "practice"
TELEGRAM_TOKEN = "8172914158:AAGHyW_q_PrJZpTiNv_X5g0DyfEcgtGykBE"
CHAT_ID = "5372494623"

api = API(access_token=OANDA_API_KEY, environment=OANDA_ENV)

SYMBOL = "US100_USD"                    # Fixed correct symbol
POSITION_SIZE = 1000
ENTRY_START = "14:30"
ENTRY_END = "15:00"
EXIT_TIME = "15:10"
already_traded_today = False
app = Flask(__name__)

# =================== BULLETPROOF TELEGRAM ===================
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": f"🤖 {message}",
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        r = requests.post(url, data=payload, timeout=10)
        if r.status_code != 200:
            print(f"Telegram error: {r.text}")
    except Exception as e:
        print(f"Telegram exception: {e}")

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
        params = {"count": count, "granularity": granularity, "price": "M"}
        r = instruments.InstrumentsCandles(instrument=SYMBOL, params=params)
        api.request(r)
        return [c for c in r.response["candles"] if c["complete"]]
    except:
        return []

# =================== STRICT FVG DETECTION ===================
def detect_fvg():
    candles = get_candles(count=10, granularity="M15")
    if len(candles) < 3:
        return None

    c0 = candles[-3]  # oldest
    c1 = candles[-2]
    c2 = candles[-1]  # newest

    h0, l0 = float(c0["mid"]["h"]), float(c0["mid"]["l"])
    h2, l2 = float(c2["mid"]["h"]), float(c2["mid"]["l"])

    if l2 > h0:  # Bullish FVG
        return {"type": "bullish", "zone_bottom": h0, "zone_top": l2}
    if h2 < l0:  # Bearish FVG
        return {"type": "bearish", "zone_bottom": h2, "zone_top": l0}
    return None

# =================== TRADE & CLOSE ===================
def place_trade(direction, fvg):
    price = get_price()
    if not price:
        return

    buffer = 0.5
    sl = round(price - buffer if direction == "long" else price + buffer, 1)
    tp = round(price + buffer*2 if direction == "long" else price - buffer*2, 1)
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

    try:
        r = orders.OrderCreate(OANDA_ACCOUNT_ID, data=data)
        api.request(r)
        send_telegram(f"FVG {direction.upper()} EXECUTED\n"
                      f"Entry: {price}\nSL: {sl} | TP: {tp}\n"
                      f"FVG Zone: {fvg['zone_bottom']}–{fvg['zone_top']}\n"
                      f"Time: {datetime.datetime.now().strftime('%H:%M')}")
    except Exception as e:
        send_telegram(f"Trade failed: {str(e)}")

def close_positions():
    try:
        r = accounts.AccountDetails(OANDA_ACCOUNT_ID)
        api.request(r)
        for pos in r.response['account']['positions']:
            if pos['instrument'] == SYMBOL and abs(float(pos['long']['units']) + float(pos['short']['units'])) > 50:
                units_to_close = str(-int(float(pos['long']['units']) + float(pos['short']['units'])))
                data = {"order": {"instrument": SYMBOL, "units": units_to_close, "type": "MARKET"}}
                orders.OrderCreate(OANDA_ACCOUNT_ID, data=data).request(api)
                send_telegram(f"Position closed at {datetime.datetime.now().strftime('%H:%M')}")
    except:
        pass

# =================== MAIN LOOP ===================
def daily_strategy():
    global already_traded_today
    send_telegram("DYLAN'S NAS100 FVG BOT JUST WOKE UP & IS HUNTING")

    while True:
        now = datetime.datetime.now()
        t = now.strftime("%H:%M")

        # Daily reset
        if now.hour == 0 and now.minute < 5:
            already_traded_today = False
            send_telegram("New day – ready to snipe FVGs")

        # Entry window
        if ENTRY_START <= t <= ENTRY_END and not already_traded_today:
            send_telegram("Scanning for FVG right now (14:30–15:00)...")
            fvg = detect_fvg()
            if fvg:
                price = get_price() or 0
                zone_low, zone_high = fvg["zone_bottom"], fvg["zone_top"]
                # Simple retest check
                if zone_low - 10 <= price <= zone_high + 10:
                    direction = "long" if fvg["type"] == "bullish" else "short"
                    place_trade(direction, fvg)
                    already_traded_today = True
                else:
                    send_telegram(f"FVG found but price {price} not in zone yet – waiting...")
            else:
                send_telegram("No clean FVG today")

        # Force close
        if t == EXIT_TIME:
            close_positions()

        time.sleep(20)

# =================== FLASK ===================
@app.route("/")
def home():
    return "Dylan's NAS100 FVG Bot – LIVE & NOTIFIED"

if __name__ == "__main__":
    Thread(target=daily_strategy, daemon=True).start()
    send_telegram("BOT FULLY STARTED – YOU WILL GET EVERY ALERT FROM NOW ON")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)