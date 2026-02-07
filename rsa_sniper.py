import os
import requests
import re
import yfinance as yf
from datetime import datetime
from edgar import *

# --- TARGET CONFIG ---
# We look for these NAMES, not Tickers.
# This fixes the "Missing Ticker" bug.
TARGET_NAMES = {
    "agape": "ATPC",
    "utime": "WTO",
    "sphere 3d": "ANY",
    "edible garden": "EDBL",
    "noodles": "NDLS"
}

set_identity("Kevin Anderson kevinand83@gmail.com")
DB_FILE = "seen_filings.txt"

def get_stock_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        try: price = stock.fast_info.last_price
        except: price = stock.info.get('currentPrice', 0.0)
            
        try:
            shares = stock.info.get('sharesOutstanding', 0)
            mcap = stock.info.get('marketCap', 0)
        except:
            shares = 0; mcap = 0
            
        if mcap > 1000000: mcap_str = f"${mcap/1000000:.2f}M"
        else: mcap_str = f"${mcap}"
        
        if shares > 1000000: shares_str = f"{shares/1000000:.2f}M"
        else: shares_str = str(shares)

        return price, shares_str, mcap_str
    except:
        return 0.0, "N/A", "N/A"

def extract_split_details(text):
    clean_text = re.sub(r'\s+', ' ', text).lower()
    ratio = 0
    match = re.search(r'1-for-([0-9]+)', clean_text)
    if match: 
        try: ratio = int(match.group(1))
        except: pass
        
    if ratio == 0:
        match = re.search(r'1:([0-9]+)', clean_text)
        if match:
            try: ratio = int(match.group(1))
            except: pass

    date_str = "Check Filing"
    date_match = re.search(r'effective (as of )?([a-z]+ [0-9]{1,2},? [0-9]{4})', clean_text)
    if date_match: date_str = date_match.group(2)
        
    return ratio, date_str

def send_telegram_msg(message):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    params = {"chat_id": chat_id, "text": message}
    try:
        requests.get(url, params=params)
    except Exception as e:
        print(f"Telegram Error: {e}")

def run_rsa_sniper():
    print(f"--- MODE: NAME HUNTER (Scanning Names, Ignoring Tickers) ---")
    
    # 5000 is safer to catch last week's stuff
    scan_depth = 5000 
    print(f"Connecting to SEC (Last {scan_depth} files)...")
    
    try:
        filings = get_filings(form=["8-K", "6-K"]).latest(scan_depth)
        print(f"SUCCESS: Downloaded {len(filings)} filings.")
    except Exception as e:
        print(f"SEC ERROR: {e}")
        return

    count_checked = 0
    
    # DEBUG: Print first 5 companies so User knows it's working
    print("--- DEBUG: Verifying Feed Data (First 5 Files) ---")
    for i in range(5):
        if i < len(filings):
            print(f"   Saw: {filings[i].company}")
    print("------------------------------------------------")

    for filing in filings:
        count_checked += 1
        
        # 1. NAME MATCH (The Fix)
        company_lower = str(filing.company).lower()
        matched_ticker = None
        
        for name_key, ticker_val in TARGET_NAMES.items():
            if name_key in company_lower:
                matched_ticker = ticker_val
                print(f"🎯 MATCH FOUND: {filing.company} -> {matched_ticker}")
                break
        
        # If not in our target list, skip
        if not matched_ticker:
            continue

        try:
            # READ TEXT
            main_text = filing.text()
            if not main_text: continue
            
            # GET DATA
            price, shares, mcap = get_stock_data(matched_ticker)
            ratio, effective_date = extract_split_details(main_text)
            
            profit_msg = "Calc Failed"
            ratio_msg = "Unknown"
            if ratio > 0:
                ratio_msg = f"1-for-{ratio}"
                if price > 0:
                    est_value = price * ratio
                    profit = est_value - price
                    profit_msg = f"${profit:.2f} per share"

            found_at = datetime.now().strftime("%I:%M %p")
            msg = (
                f"🚨 TARGET FOUND: {matched_ticker} 🚨\n"
                f"-------------------------\n"
                f"💰 EST. PROFIT: {profit_msg}\n"
                f"-------------------------\n"
                f"Price: ${price:.2f}\n"
                f"Split: {ratio_msg}\n"
                f"Float: {shares}\n"
                f"Market Cap: {mcap}\n"
                f"-------------------------\n"
                f"Effective: {effective_date}\n"
                f"Found: {found_at} ET\n"
                f"Link: {filing.url}"
            )
            
            print(f">>> SENDING ALERT FOR {matched_ticker} <<<")
            send_telegram_msg(msg)

        except Exception as e:
            print(f"Error reading {matched_ticker}: {e}")

    print(f"Run Complete. Scanned {count_checked} files.")

if __name__ == "__main__":
    run_rsa_sniper()
