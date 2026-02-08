import os
import requests
import re
import yfinance as yf
from datetime import datetime, time
from edgar import *

set_identity("Kevin Anderson kevinand83@gmail.com")

# --- THE VERIFIED TARGET LIST (No Guessing) ---
VERIFIED_DATA = {
    "WTO": {"ratio": 5, "effective": "2026-02-17", "cutoff": "2026-02-13"}, 
    "ANY": {"ratio": 10, "effective": "2026-02-10", "cutoff": "2026-02-09"},
    "ATPC": {"ratio": 50, "effective": "2026-02-10", "cutoff": "2026-02-09"}
}

def get_live_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        price = stock.fast_info.last_price
        return float(price) if price else 0.0
    except: return 0.0

def send_telegram_msg(message):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.get(url, params={"chat_id": chat_id, "text": message})

def run_rsa_sniper():
    now = datetime.now()
    print(f"Running Sentry at {now.strftime('%H:%M:%S')}")

    for ticker, info in VERIFIED_DATA.items():
        price = get_live_price(ticker)
        profit = (price * info["ratio"]) - price
        cutoff_date = datetime.strptime(info["cutoff"], "%Y-%m-%d").date()
        
        # 1. THE ALARM LOGIC (Triggers if it's the Cutoff Day)
        is_cutoff_day = (now.date() == cutoff_date)
        is_final_warning = (now.hour == 15 and now.minute >= 45) # 3:45 PM EST

        status = "🟢 ACTIVE"
        if is_cutoff_day and is_final_warning:
            status = "🚨 FINAL WARNING: BUY NOW"
        elif is_cutoff_day:
            status = "⚠️ CUTOFF TODAY"

        msg = (
            f"{status}: {ticker}\n"
            f"-------------------------\n"
            f"PROFIT: ${profit:.2f}\n"
            f"Price: ${price:.2f}\n"
            f"Split: 1-for-{info['ratio']}\n"
            f"Action: Buy 1 share before 4PM EST on {info['cutoff']}\n"
            f"Link: https://www.google.com/finance/quote/{ticker}:NASDAQ"
        )
        send_telegram_msg(msg)

if __name__ == "__main__":
    run_rsa_sniper()
