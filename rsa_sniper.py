import os
import requests
import re
import yfinance as yf
from datetime import datetime
from edgar import *

# --- CONFIGURATION ---
# WE ARE HARD-CODING THE TARGETS SO YOU DON'T HAVE TO TYPE ANYTHING.
TARGET_LIST = ["ATPC", "WTO", "ANY", "EDBL", "NDLS"]
# ---------------------

set_identity("Kevin Anderson kevinand83@gmail.com")
DB_FILE = "seen_filings.txt"

def get_stock_data(ticker):
    print(f"   -> Fetching Finance Data for {ticker}...")
    try:
        stock = yf.Ticker(ticker)
        # Try Fast Info
        try: price = stock.fast_info.last_price
        except: price = stock.info.get('currentPrice', 0.0)
            
        try:
            shares = stock.info.get('sharesOutstanding', 0)
            mcap = stock.info.get('marketCap', 0)
        except:
            shares = 0; mcap = 0
            
        # Format
        if mcap > 1000000: mcap_str = f"${mcap/1000000:.2f}M"
        else: mcap_str = f"${mcap}"
        
        if shares > 1000000: shares_str = f"{shares/1000000:.2f}M"
        else: shares_str = str(shares)

        return price, shares_str, mcap_str
    except:
        return 0.0, "N/A", "N/A"

def extract_split_details(text):
    """Finds '1-for-X' or '1:X' ratio."""
    clean_text = re.sub(r'\s+', ' ', text).lower()
    ratio = 0
    
    # Pattern 1: "1-for-50"
    match = re.search(r'1-for-([0-9]+)', clean_text)
    if match: 
        try: ratio = int(match.group(1))
        except: pass
        
    # Pattern 2: "1:50"
    if ratio == 0:
        match = re.search(r'1:([0-9]+)', clean_text)
        if match:
            try: ratio = int(match.group(1))
            except: pass

    # Find Date
    date_str = "Check Filing"
    date_match = re.search(r'effective (as of )?([a-z]+ [0-9]{1,2},? [0-9]{4})', clean_text)
    if date_match:
        date_str = date_match.group(2)
        
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
    print(f"--- MODE: TARGET MANHUNT ({TARGET_LIST}) ---")
    print(f"--- SCAN DEPTH: 3000 Filings (~4 Days) ---")

    print(f"Connecting to SEC...")
    try:
        # Added 6-K for WTO and ATPC
        filings = get_filings(form=["8-K", "6-K"]).latest(3000)
        print(f"SUCCESS: Downloaded list of {len(filings)} filings.")
    except Exception as e:
        print(f"SEC ERROR: {e}")
        return

    count_found = 0

    for filing in filings:
        # 1. TICKER REPAIR
        ticker = "UNKNOWN"
        try:
            if filing.ticker: ticker = filing.ticker
            
            # Manual Fixes
            co = filing.company.lower()
            if "agape" in co: ticker = "ATPC"
            if "utime" in co: ticker = "WTO"
            if "sphere 3d" in co: ticker = "ANY"
            if "edible garden" in co: ticker = "EDBL"
            if "noodles" in co: ticker = "NDLS"
            
            ticker = str(ticker).upper()
        except:
            pass

        # 2. TARGET FILTER (Only look for the list)
        if ticker not in TARGET_LIST:
            continue

        print(f"🎯 FOUND TARGET FILE: {ticker} (Date: {filing.filing_date})")

        try:
            # READ TEXT
            main_text = filing.text()
            if not main_text: continue
            
            # EXTRACT DATA
            price, shares, mcap = get_stock_data(ticker)
            ratio, effective_date = extract_split_details(main_text)
            
            # CALCULATE PROFIT
            profit_msg = "Calc Failed"
            ratio_msg = "Unknown"
            
            if ratio > 0:
                ratio_msg = f"1-for-{ratio}"
                if price > 0:
                    # Profit Logic: (Price * Ratio) - Price
                    # This assumes rounding up to 1 share.
                    est_value = price * ratio
                    profit = est_value - price
                    profit_msg = f"${profit:.2f} per share"

            found_at = datetime.now().strftime("%I:%M %p")
            msg = (
                f"🚨 TARGET FOUND: {ticker} 🚨\n"
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
            
            print(f">>> SENDING ALERT FOR {ticker} <<<")
            send_telegram_msg(msg)
            count_found += 1

        except Exception as e:
            print(f"Error processing {ticker}: {e}")

    print(f"Run Complete. Found {count_found} targets.")

if __name__ == "__main__":
    run_rsa_sniper()
