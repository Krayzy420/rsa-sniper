import os
import requests
import re
import yfinance as yf
from datetime import datetime
from edgar import *
from dateutil import parser 

set_identity("Kevin Anderson kevinand83@gmail.com")
DB_FILE = "seen_filings.txt"

# --- THE "NO-FAIL" MAP ---
# I am locking in the WTO info you provided to override the old SEC data.
OVERRIDE_DATA = {
    "WTO": {"ratio": 5, "effective": "February 17, 2026"}, 
    "ANY": {"ratio": 10, "effective": "February 10, 2026"},
    "ATPC": {"ratio": 50, "effective": "February 10, 2026"}
}

FORCE_TEST_TICKER = os.environ.get('TEST_TICKER')
if FORCE_TEST_TICKER:
    FORCE_TEST_TICKER = FORCE_TEST_TICKER.strip().upper()

def get_stock_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        # Get the most recent price possible
        price = stock.fast_info.last_price
        if price is None or price <= 0:
            price = stock.info.get('regularMarketPrice', 0.0)
        if price <= 0:
            price = stock.info.get('currentPrice', 0.0)
        return float(price)
    except:
        return 0.0

def analyze_split_data(ticker, text):
    # Check if we have manually verified data first
    if ticker in OVERRIDE_DATA:
        return OVERRIDE_DATA[ticker]["ratio"], OVERRIDE_DATA[ticker]["effective"], False

    clean_text = re.sub(r'\s+', ' ', text).lower()
    ratio = 0
    
    # Pattern for 2026 filings only
    patterns = [r'1-for-([0-9]+)', r'every\s+([0-9]+)\s+.*into\s+one']
    for p in patterns:
        match = re.search(p, clean_text)
        if match:
            try:
                val = int(match.group(1))
                if val > 1: ratio = val; break
            except: continue

    date_str = "Unknown"
    is_expired = False
    # Only look for 2026 dates to avoid the Nov 2025 trap
    date_match = re.search(r'([a-z]+ [0-9]{1,2},? 2026)', clean_text)
    if date_match:
        date_str = date_match.group(1)
        try:
            eff_date_obj = parser.parse(date_str)
            if eff_date_obj.date() < datetime.now().date():
                is_expired = True
        except: pass
        
    return ratio, date_str, is_expired

def check_gold_status(text):
    if not text: return "NONE"
    clean_text = re.sub(r'\s+', ' ', text).lower()
    if any(p in clean_text for p in ["cash in lieu", "paid in cash"]):
        return "BAD"
    good_stuff = ["round up", "rounded up", "whole share", "upward adjustment"]
    if any(g in clean_text for g in good_stuff):
        return "GUARANTEED"
    return "NONE"

def send_telegram_msg(message):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try: requests.get(url, params={"chat_id": chat_id, "text": message})
    except: pass

def run_rsa_sniper():
    print(f"Connecting to SEC...")
    if FORCE_TEST_TICKER:
        try:
            company = Company(FORCE_TEST_TICKER)
            # Pull more filings so we can find the 2026 one
            filings = company.get_filings(form=["8-K", "6-K"]).latest(40)
        except: return
    else:
        filings = get_filings(form=["8-K", "6-K"]).latest(100)

    for filing in filings:
        ticker = FORCE_TEST_TICKER if FORCE_TEST_TICKER else "UNKNOWN"
        # ... (ticker resolution logic) ...
        
        try:
            main_text = filing.text()
            status = check_gold_status(main_text)
            
            if status == "GUARANTEED":
                price = get_stock_data(ticker)
                ratio, eff_date, is_expired = analyze_split_data(ticker, main_text)
                
                # Only alert if it's the 2026 deal
                if "2026" in str(eff_date) or ticker in OVERRIDE_DATA:
                    header = "🚨 LIVE RSA" if not is_expired else "⛔ EXPIRED"
                    # Profit is (New Share Value) - (Cost of 1 share)
                    profit = (price * ratio) - price if price > 0 else 0.0
                    
                    msg = (
                        f"{header}: {ticker}\n"
                        f"Target Profit: ${profit:.2f}\n"
                        f"Current Price: ${price:.2f}\n"
                        f"Split: 1-for-{ratio}\n"
                        f"Effective Date: {eff_date}\n"
                        f"Link: {filing.url}"
                    )
                    send_telegram_msg(msg)
                    if FORCE_TEST_TICKER: return
        except: continue

if __name__ == "__main__":
    run_rsa_sniper()
