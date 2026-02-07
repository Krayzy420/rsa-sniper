import os
import requests
import re
import yfinance as yf
from datetime import datetime
from edgar import *

# --- CONFIGURATION ---
TARGET_LIST = ["ATPC", "WTO", "ANY", "EDBL", "NDLS", "SERV", "MULN", "GREE"] 
# ---------------------

set_identity("Kevin Anderson kevinand83@gmail.com")
DB_FILE = "seen_filings.txt"

def get_stock_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        
        # 1. Try Real-Time Price
        try: price = stock.fast_info.last_price
        except: price = stock.info.get('currentPrice', 0.0)
        
        # 2. Backup Price
        if price is None or price == 0:
            price = stock.info.get('previousClose', 0.0)
            
        try:
            shares = stock.info.get('sharesOutstanding', 0)
            mcap = stock.info.get('marketCap', 0)
        except:
            shares = 0; mcap = 0
            
        # Format for display
        if mcap > 1000000: mcap_str = f"${mcap/1000000:.2f}M"
        else: mcap_str = f"${mcap}"
        
        if shares > 1000000: shares_str = f"{shares/1000000:.2f}M"
        else: shares_str = str(shares)

        return float(price), shares_str, mcap_str
    except:
        return 0.0, "N/A", "N/A"

def extract_split_details(text):
    clean_text = re.sub(r'\s+', ' ', text).lower()
    ratio = 0
    
    # 1. FILTER OUT RANGES (Fix for NDLS)
    no_range_text = re.sub(r'range of 1-for-[0-9]+ to 1-for-[0-9]+', '', clean_text)
    
    # 2. LOOK FOR "1-for-X"
    match = re.search(r'1-for-([0-9]+)', no_range_text)
    if match: 
        try: ratio = int(match.group(1))
        except: pass
        
    # 3. LOOK FOR "X-for-1 Consolidation" (Fix for WTO)
    if ratio == 0:
        match = re.search(r'([0-9]+)-for-1 (share )?consolidation', clean_text)
        if match:
            try: ratio = int(match.group(1))
            except: pass

    # 4. LOOK FOR "1:X"
    if ratio == 0:
        match = re.search(r'1:([0-9]+)', clean_text)
        if match:
            try: ratio = int(match.group(1))
            except: pass

    # Find Date
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
    print(f"--- MODE: NAME HUNTER (Intelligent Regex) ---")
    
    scan_depth = 3000 
    print(f"Connecting to SEC (Last {scan_depth} files)...")
    
    try:
        filings = get_filings(form=["8-K", "6-K"]).latest(scan_depth)
        print(f"SUCCESS: Downloaded {len(filings)} filings.")
    except Exception as e:
        print(f"SEC ERROR: {e}")
        return

    # TRACKING SET to stop Duplicates
    sent_tickers = set()

    for filing in filings:
        # 1. NAME MATCH
        company_lower = str(filing.company).lower()
        matched_ticker = None
        
        if "agape" in company_lower: matched_ticker = "ATPC"
        elif "utime" in company_lower: matched_ticker = "WTO"
        elif "sphere 3d" in company_lower: matched_ticker = "ANY"
        elif "edible garden" in company_lower: matched_ticker = "EDBL"
        elif "noodles" in company_lower: matched_ticker = "NDLS"
        
        if not matched_ticker:
            continue

        # 2. DUPLICATE CHECK
        if matched_ticker in sent_tickers:
            continue

        print(f"🎯 ANALYZING: {matched_ticker}...")

        try:
            # READ TEXT
            main_text = filing.text()
            if not main_text: continue
            
            # EXTRACT DATA
            price, shares, mcap = get_stock_data(matched_ticker)
            ratio, effective_date = extract_split_details(main_text)
            
            # CALCULATE PROFIT
            profit_msg = "Unknown"
            ratio_msg = "Unknown"
            
            if ratio > 0:
                ratio_msg = f"1-for-{ratio}"
                if price > 0:
                    est_value = price * ratio
                    profit = est_value - price
                    profit_msg = f"${profit:.2f}"
            
            math_proof = ""
            if ratio > 0 and price > 0:
                math_proof = f"(Math: ${price:.2f} x {ratio} - ${price:.2f})"

            found_at = datetime.now().strftime("%I:%M %p")
            msg = (
                f"🚨 UPDATED INTEL: {matched_ticker} 🚨\n"
                f"-------------------------\n"
                f"💰 EST. PROFIT: {profit_msg}\n"
                f"{math_proof}\n"
                f"-------------------------\n"
                f"Price: ${price:.2f}\n"
                f"Split: {ratio_msg}\n"
                f"Float: {shares}\n"
                f"-------------------------\n"
                f"Effective: {effective_date}\n"
                f"Link: {filing.url}"
            )
            
            print(f">>> SENDING ALERT FOR {matched_ticker} <<<")
            send_telegram_msg(msg)
            
            sent_tickers.add(matched_ticker)

        except Exception as e:
            print(f"Error reading {matched_ticker}: {e}")

    print(f"Run Complete.")

if __name__ == "__main__":
    run_rsa_sniper()
