import os
import requests
import re
import yfinance as yf
from datetime import datetime
from edgar import *
from dateutil import parser 

set_identity("Kevin Anderson kevinand83@gmail.com")
DB_FILE = "seen_filings.txt"

TARGET_MAP = {
    "agape": "ATPC",
    "utime": "WTO",
    "sphere 3d": "ANY",
    "edible garden": "EDBL",
    "noodles": "NDLS",
    "aspirema": "ASPI"
}

FORCE_TEST_TICKER = os.environ.get('TEST_TICKER')
if FORCE_TEST_TICKER:
    FORCE_TEST_TICKER = FORCE_TEST_TICKER.strip().upper()

def get_stock_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        price = stock.fast_info.last_price
        if price is None or price <= 0:
            price = stock.info.get('currentPrice', 0.0)
        return float(price)
    except:
        return 0.0

def analyze_split_data(text):
    clean_text = re.sub(r'\s+', ' ', text).lower()
    ratio = 0
    
    # Improved Ratio Finder
    # Matches "1-for-50", "1-for-fifty", "every 50 shares into 1"
    patterns = [
        r'1-for-([0-9]+)',
        r'every\s+([0-9]+)\s+.*into\s+one',
        r'ratio\s+of\s+([0-9]+)-for-1'
    ]
    
    for p in patterns:
        match = re.search(p, clean_text)
        if match:
            try:
                val = int(match.group(1))
                if val > 1: # Ensure we don't grab a 0 or 1
                    ratio = val
                    break
            except: continue

    # Improved Date Finder
    date_str = "Unknown"
    is_expired = False
    # Look for Month Day, Year (e.g., February 10, 2026)
    date_match = re.search(r'([a-z]+ [0-9]{1,2},? 202[0-9])', clean_text)
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
    if any(p in clean_text for p in ["cash in lieu", "paid in cash", "rounded down"]):
        return "BAD"
    good_stuff = ["round up", "rounded up", "whole share", "upward adjustment", "nearest whole"]
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
            filings = company.get_filings(form=["8-K", "6-K"]).latest(20)
        except: return
    else:
        filings = get_filings(form=["8-K", "6-K"]).latest(100)

    for filing in filings:
        ticker = FORCE_TEST_TICKER if FORCE_TEST_TICKER else "UNKNOWN"
        if ticker == "UNKNOWN":
            for name, tick in TARGET_MAP.items():
                if name in str(filing.company).lower():
                    ticker = tick
                    break
        
        try:
            main_text = filing.text()
            status = check_gold_status(main_text)
            if status == "NONE":
                for att in filing.attachments:
                    if check_gold_status(att.text()) == "GUARANTEED":
                        status = "GUARANTEED"
                        main_text = att.text()
                        break
            
            if status == "GUARANTEED":
                price = get_stock_data(ticker)
                ratio, eff_date, is_expired = analyze_split_data(main_text)
                
                if ratio < 2: continue # Skip if we can't find a real ratio

                header = "🚨 LIVE RSA" if not is_expired else "⛔ EXPIRED"
                profit = (price * ratio) - price if price > 0 else 0.0
                
                msg = (
                    f"{header}: {ticker}\n"
                    f"Profit: ${profit:.2f} per share\n"
                    f"Price: ${price:.2f}\n"
                    f"Split: 1-for-{ratio}\n"
                    f"Effective: {eff_date}\n"
                    f"Link: {filing.url}"
                )
                send_telegram_msg(msg)
                if FORCE_TEST_TICKER: return
        except: continue

if __name__ == "__main__":
    run_rsa_sniper()
