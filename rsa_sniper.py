import os
imporimport os
import requests
import re
import yfinance as yf
from datetime import datetime
from edgar import *

# --- CONFIGURATION ---
set_identity("Kevin Anderson kevinand83@gmail.com")
DB_FILE = "seen_filings.txt"
FORCE_TEST = True 

# --- THE VERIFIED TARGET LIST ---
VERIFIED_DATA = {
    "WTO": {"ratio": 5, "effective": "2026-02-17", "cutoff": "2026-02-13"}, 
    "ANY": {"ratio": 10, "effective": "2026-02-10", "cutoff": "2026-02-09"},
    "ATPC": {"ratio": 50, "effective": "2026-02-10", "cutoff": "2026-02-09"},
    "HERZ": {"ratio": 10, "effective": "2026-02-09", "cutoff": "2026-02-06"}
}

def load_seen_filings():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return set(line.strip() for line in f)
    return set()

def save_seen_filing(accession_number):
    with open(DB_FILE, "a") as f:
        f.write(f"{accession_number}\n")

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
    try:
        requests.get(url, params={"chat_id": chat_id, "text": message, "disable_web_page_preview": "true"})
    except Exception as e:
        print(f"   -> Telegram Fail: {e}", flush=True)

def run_rsa_sniper():
    print("SYSTEM ONLINE: Starting Sentry Scan...", flush=True)
    now = datetime.now()
    seen_filings = load_seen_filings()
    
    for ticker, info in VERIFIED_DATA.items():
        print(f"Checking {ticker}...", flush=True)
        price = get_live_price(ticker)
        cutoff_date = datetime.strptime(info["cutoff"], "%Y-%m-%d").date()
        
        # --- SMART PROFIT LOGIC ---
        if now.date() > cutoff_date:
            # POST-SPLIT (Held): Price is High. Work backward to find gain.
            # Value is Current Price. Cost was roughly (Current Price / Ratio).
            status = "✅ SPLIT CONFIRMED / HELD"
            profit = price - (price / info["ratio"])
            profit_label = "REALIZED GAIN"
        
        elif now.date() == cutoff_date:
            # CUTOFF DAY: Price is Low. Multiply forward.
            status = "🚨 CUTOFF TODAY (VERIFIED ROUNDUP)"
            profit = (price * info["ratio"]) - price
            profit_label = "PROJECTED PROFIT"
            
        else:
            # ACTIVE: Price is Low. Multiply forward.
            status = "🟢 ACTIVE"
            profit = (price * info["ratio"]) - price
            profit_label = "PROJECTED PROFIT"

        # --- DUPLICATE GUARD ---
        alert_id = f"{ticker}_{status}_{now.strftime('%Y-%m-%d')}"
        
        if not FORCE_TEST and alert_id in seen_filings:
            print(f"   -> Skipped {ticker} (Already sent today)", flush=True)
            continue 

        msg = (
            f"{status}: {ticker}\n"
            f"-------------------------\n"
            f"💰 {profit_label}: ${profit:.2f}\n"
            f"📉 Price: ${price:.2f}\n"
            f"➗ Split: 1-for-{info['ratio']}\n"
            f"⏳ Buy Before: 4PM EST on {info['cutoff']}\n"
            f"🔗 Link: https://www.google.com/finance/quote/{ticker}:NASDAQ"
        )
        
        send_telegram_msg(msg)
        save_seen_filing(alert_id)

    print("SCAN COMPLETE.", flush=True)

if __name__ == "__main__":
    run_rsa_sniper()t requests
import re
import yfinance as yf
from datetime import datetime
from edgar import *

# --- CONFIGURATION ---
set_identity("Kevin Anderson kevinand83@gmail.com")
DB_FILE = "seen_filings.txt"
# SET THIS TO TRUE TO FORCE A TEST MESSAGE RIGHT NOW
FORCE_TEST = True 

# --- THE VERIFIED TARGET LIST ---
VERIFIED_DATA = {
    "WTO": {"ratio": 5, "effective": "2026-02-17", "cutoff": "2026-02-13"}, 
    "ANY": {"ratio": 10, "effective": "2026-02-10", "cutoff": "2026-02-09"},
    "ATPC": {"ratio": 50, "effective": "2026-02-10", "cutoff": "2026-02-09"},
    "HERZ": {"ratio": 10, "effective": "2026-02-09", "cutoff": "2026-02-06"}
}

def load_seen_filings():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return set(line.strip() for line in f)
    return set()

def save_seen_filing(accession_number):
    with open(DB_FILE, "a") as f:
        f.write(f"{accession_number}\n")

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
    try:
        # We add disable_web_page_preview=True to stop the huge link preview
        print(f"   -> Sending Telegram for {message.split(':')[0]}...", flush=True)
        requests.get(url, params={"chat_id": chat_id, "text": message, "disable_web_page_preview": "true"})
    except Exception as e:
        print(f"   -> Telegram Fail: {e}", flush=True)

def run_rsa_sniper():
    print("SYSTEM ONLINE: Starting Sentry Scan...", flush=True)
    now = datetime.now()
    seen_filings = load_seen_filings()
    
    for ticker, info in VERIFIED_DATA.items():
        print(f"Checking {ticker}...", flush=True)
        price = get_live_price(ticker)
        cutoff_date = datetime.strptime(info["cutoff"], "%Y-%m-%d").date()
        
        # --- PROFIT CALCULATION ---
        # (New Price) - (Old Price)
        # New Price = Current Price * Ratio
        profit = (price * info["ratio"]) - price

        # --- STATUS LOGIC ---
        if now.date() > cutoff_date:
            status = "✅ SPLIT CONFIRMED / HELD"
        elif now.date() == cutoff_date:
            status = "🚨 CUTOFF TODAY (VERIFIED ROUNDUP)"
        else:
            status = "🟢 ACTIVE"

        # --- DUPLICATE GUARD ---
        alert_id = f"{ticker}_{status}_{now.strftime('%Y-%m-%d')}"
        
        # IF FORCE_TEST IS ON, WE IGNORE THE GUARD
        if not FORCE_TEST and alert_id in seen_filings:
            print(f"   -> Skipped {ticker} (Already sent today)", flush=True)
            continue 

        msg = (
            f"{status}: {ticker}\n"
            f"-------------------------\n"
            f"💰 PROFIT: ${profit:.2f}\n"
            f"📉 Price: ${price:.2f}\n"
            f"➗ Split: 1-for-{info['ratio']}\n"
            f"⏳ Buy Before: 4PM EST on {info['cutoff']}\n"
            f"🔗 Link: https://www.google.com/finance/quote/{ticker}:NASDAQ"
        )
        
        send_telegram_msg(msg)
        
        save_seen_filing(alert_id)

    print("SCAN COMPLETE.", flush=True)

# --- START ENGINE ---
if __name__ == "__main__":
    run_rsa_sniper()
