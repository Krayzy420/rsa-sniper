import os
import requests
import re
import yfinance as yf
from datetime import datetime
from edgar import *

set_identity("Kevin Anderson kevinand83@gmail.com")

DB_FILE = "seen_filings.txt"

# READ THE TEST BUTTON INPUT
FORCE_TEST_TICKER = os.environ.get('TEST_TICKER')
if FORCE_TEST_TICKER == "": 
    FORCE_TEST_TICKER = None

def load_seen_filings():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return set(line.strip() for line in f)
    return set()

def save_seen_filing(accession_number):
    with open(DB_FILE, "a") as f:
        f.write(f"{accession_number}\n")

def get_stock_data(ticker):
    if ticker == "UNKNOWN": return "N/A", "N/A", "N/A"
    try:
        stock = yf.Ticker(ticker)
        info = stock.fast_info
        price = info.last_price
        if not price: 
            price = stock.info.get('currentPrice', 0.0)
            if not price: price = stock.info.get('previousClose', 0.0)
        
        try:
            full_info = stock.info
            shares = full_info.get('sharesOutstanding', 0)
            mcap = full_info.get('marketCap', 0)
        except:
            shares = 0; mcap = 0
        
        if mcap and mcap > 1000000: mcap_str = f"${mcap/1000000:.2f}M"
        else: mcap_str = f"${mcap}"
            
        if shares and shares > 1000000: shares_str = f"{shares/1000000:.2f}M"
        else: shares_str = str(shares)

        return f"{price:.2f}", shares_str, mcap_str
    except:
        return "N/A", "N/A", "N/A"

def send_telegram_msg(message):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    params = {"chat_id": chat_id, "text": message}
    try:
        requests.get(url, params=params)
    except Exception as e:
        print(f"Telegram Error: {e}")

def check_text_for_gold(text):
    if not text: return False, False
    clean_text = re.sub(r'\s+', ' ', text).lower()
    
    # 1. POSITIVE (Round Up)
    pos_patterns = [r"round(ed|ing)? up", r"next whole share", r"nearest whole share", r"upwardly adjusted"]
    has_pos = any(re.search(p, clean_text) for p in pos_patterns)

    # 2. NEGATIVE (Cash)
    neg_patterns = [r"cash in lieu", r"cash payment", r"rounded down"]
    has_neg = any(re.search(p, clean_text) for p in neg_patterns)

    return has_pos, has_neg

def run_rsa_sniper():
    print(f"--- STARTING RUN (Test Ticker: {FORCE_TEST_TICKER}) ---")
    
    # SCANNING 9000 to catch everything
    scan_depth = 9000 
    print(f"Connecting to SEC (Scanning last {scan_depth} filings)...")
    
    try:
        filings = get_filings().latest(scan_depth)
        print(f"SUCCESS: Downloaded {len(filings)} filings.")
    except Exception as e:
        print(f"CRITICAL SEC ERROR: {e}")
        return

    # ADDED "6-K" HERE TO CATCH FOREIGN STOCKS LIKE WTO AND ATPC
    target_forms = ["8-K", "6-K", "DEF 14A", "PRE 14A", "14C", "DEF 14C"]
    seen_filings = load_seen_filings()
    count_checked = 0
    
    found_at = datetime.now().strftime("%I:%M %p")

    for filing in filings:
        if filing.form not in target_forms:
            continue
            
        count_checked += 1
        
        # Ticker Repair
        try:
            ticker = filing.ticker
            if not ticker and "noodles" in filing.company.lower(): ticker = "NDLS"
            if not ticker and "edible garden" in filing.company.lower(): ticker = "EDBL"
            if not ticker and "utime" in filing.company.lower(): ticker = "WTO"
            if not ticker and "agape" in filing.company.lower(): ticker = "ATPC"
            if not ticker: ticker = "UNKNOWN"
        except:
            ticker = "UNKNOWN"

        # 1. Test Mode Logic
        if FORCE_TEST_TICKER and ticker != FORCE_TEST_TICKER:
            continue
            
        # 2. Normal Mode Logic
        if not FORCE_TEST_TICKER and filing.accession_number in seen_filings:
            continue

        if count_checked % 200 == 0:
            print(f"Scanning... ({count_checked} relevant files checked)")

        try:
            # PHASE 1: Main Text
            main_text = filing.text()
            if not main_text: continue
            
            clean_main = re.sub(r'\s+', ' ', main_text).lower()
            if "reverse" not in clean_main and "split" not in clean_main:
                continue

            has_pos, has_neg = check_text_for_gold(main_text)
            
            # PHASE 2: Attachments (Drill Down)
            if not has_pos and not has_neg:
                for attachment in filing.attachments:
                    try:
                        att_text = attachment.text()
                        p, n = check_text_for_gold(att_text)
                        if p: has_pos = True
                        if n: has_neg = True
                        if has_pos or has_neg: break 
                    except:
                        continue

            if has_pos and not has_neg:
                # MATCH FOUND!
                price, shares, mcap = get_stock_data(ticker)
                
                msg = (
                    f"RSA GOLD DETECTED\n"
                    f"------------------\n"
                    f"Ticker: {ticker}\n"
                    f"Price: ${price}\n"
                    f"Float/OS: {shares}\n"
                    f"Market Cap: {mcap}\n"
                    f"------------------\n"
                    f"Filing Date: {filing.filing_date}\n"
                    f"Popped At: {found_at}\n"
                    f"Link: {filing.url}"
                )
                
                print(f">>> ALARM TRIGGERED for {ticker} <<<")
                send_telegram_msg(msg)
                
                if not FORCE_TEST_TICKER:
                    save_seen_filing(filing.accession_number)

        except Exception as e:
            pass

    print(f"Run Complete. Scanned {count_checked} relevant documents.")

if __name__ == "__main__":
    run_rsa_sniper()
