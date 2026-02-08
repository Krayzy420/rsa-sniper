import os
import requests
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
        print(f"   -> Sending Telegram for {message.split(':')[0]}...", flush=True)
        requests.get(url, params={"chat_id": chat_id, "text": message})
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
        
        # --- STATUS LOGIC ---
        if now.date() > cutoff_date:
            status = "✅ SPLIT CONFIRMED / HELD"
        elif now.date() == cutoff_date:
            status = "🚨 CUTOFF TODAY (VERIFIED ROUNDUP)"
        else:
            status = "🟢 ACTIVE"

        # --- DUPLICATE GUARD ---
        # We create a unique ID for this specific message
        alert_id = f"{ticker}_{status}_{now.strftime('%Y-%m-%d')}"
        
        # IF FORCE_TEST IS ON, WE IGNORE THE GUARD
        if not FORCE_TEST and alert_id in seen_filings:
            print(f"   -> Skipped {ticker} (Already sent today)", flush=True)
            continue 

        msg = (
            f"{status}: {ticker}\n"
            f"-------------------------\n"
            f"Ratio: 1-for-{info['ratio']}\n"
            f"Price: ${price:.2f}\n"
            f"Action: Buy before 4PM EST on {info['cutoff']}\n"
        )
        
        send_telegram_msg(msg)
        
        # Remember we sent it
        save_seen_filing(alert_id)

    print("SCAN COMPLETE.", flush=True)

# --- START ENGINE ---
# This runs the code immediately
run_rsa_sniper()
