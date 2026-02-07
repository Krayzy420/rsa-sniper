import os
import requests
import re
import yfinance as yf
from datetime import datetime
from edgar import *
from dateutil import parser 

set_identity("Kevin Anderson kevinand83@gmail.com")
DB_FILE = "seen_filings.txt"

# --- TARGET MAP (Fixes Missing Tickers) ---
TARGET_MAP = {
    "agape": "ATPC",
    "utime": "WTO",
    "sphere 3d": "ANY",
    "edible garden": "EDBL",
    "noodles": "NDLS",
    "aspirema": "ASPI",
    "first foundation": "FFWM",
    "catheter": "VTAK",
    "groupon": "GRPN",
    "muln": "MULN",
    "gree": "GREE"
}

# --- FORCE LIVE MODE (Max 500 Files) ---
# We are locking this to 500 to prevent crashing.
SCAN_DEPTH = 500

def load_seen_filings():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return set(line.strip() for line in f)
    return set()

def save_seen_filing(accession_number):
    with open(DB_FILE, "a") as f:
        f.write(f"{accession_number}\n")

def get_stock_data(ticker):
    if ticker == "UNKNOWN": return 0.0, "N/A", "N/A"
    try:
        stock = yf.Ticker(ticker)
        try: price = stock.fast_info.last_price
        except: price = stock.info.get('currentPrice', 0.0)
        
        if price is None or price == 0:
            price = stock.info.get('previousClose', 0.0)
            
        return float(price), "N/A", "N/A"
    except:
        return 0.0, "N/A", "N/A"

def analyze_split_data(text):
    clean_text = re.sub(r'\s+', ' ', text).lower()
    ratio = 0
    
    # 1. GET RATIO
    no_range_text = re.sub(r'range of 1-for-[0-9]+ to 1-for-[0-9]+', '', clean_text)
    match = re.search(r'1-for-([0-9]+)', no_range_text)
    if match: 
        try: ratio = int(match.group(1))
        except: pass
    
    if ratio == 0:
        match = re.search(r'([0-9]+)-for-1 (share )?consolidation', clean_text)
        if match:
            try: ratio = int(match.group(1))
            except: pass

    # 2. DATE & EXPIRY
    date_str = "Unknown"
    is_expired = False
    date_match = re.search(r'effective (as of )?([a-z]+ [0-9]{1,2},? [0-9]{4})', clean_text)
    if date_match:
        date_str = date_match.group(2)
        try:
            eff_date_obj = parser.parse(date_str)
            now = datetime.now()
            if eff_date_obj < now:
                is_expired = True
        except:
            pass
    return ratio, date_str, is_expired

def check_gold_status(text):
    if not text: return "NONE"
    clean_text = re.sub(r'\s+', ' ', text).lower()

    # 1. KILLER PHRASES (Trash)
    bad_patterns = [r"cash (payment )?in lieu", r"paid in cash", r"rounded down"]
    if any(re.search(p, clean_text) for p in bad_patterns):
        return "BAD"

    # 2. GOLD PHRASES (Round Up)
    good_patterns = [
        r"round(ed|ing)? up",
        r"whole share",
        r"upward adjustment",
        r"nearest whole number",
        r"no fractional shares.*issued"
    ]
    if any(re.search(p, clean_text) for p in good_patterns):
        return "GUARANTEED"

    return "NONE"

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
    print(f"--- MODE: LIVE SNIPER (Last 500 Files) ---")
    print(f"Connecting to SEC...")
    try:
        filings = get_filings(form=["8-K", "6-K"]).latest(SCAN_DEPTH)
        print(f"SUCCESS: Downloaded {len(filings)} filings.")
    except Exception as e:
        print(f"SEC ERROR: {e}")
        return

    seen_filings = load_seen_filings()
    count_checked = 0

    for filing in filings:
        # 1. IDENTIFY TICKER
        ticker = "UNKNOWN"
        try:
            if filing.ticker: ticker = filing.ticker
            # Fix Unknowns using Map
            company_lower = str(filing.company).lower()
            for name_key, ticker_val in TARGET_MAP.items():
                if name_key in company_lower:
                    ticker = ticker_val
                    break
            ticker = str(ticker).upper()
        except:
            pass

        # 2. FILTER: SKIP SEEN FILES (Strict Live Mode)
        if filing.accession_number in seen_filings: continue

        count_checked += 1
        if count_checked % 50 == 0: print(f"Scanning... Checked {count_checked} docs")

        try:
            main_text = filing.text()
            if not main_text: continue
            
            # 3. CHECK STATUS
            status = check_gold_status(main_text)
            
            if status == "NONE":
                for attachment in filing.attachments:
                    try:
                        att_text = attachment.text()
                        att_status = check_gold_status(att_text)
                        if att_status == "GUARANTEED": 
                            status = "GUARANTEED"
                            main_text = att_text
                            break
                        if att_status == "BAD":
                            status = "BAD"
                            break
                    except:
                        continue
            
            # 4. ALERT IF GUARANTEED
            if status == "GUARANTEED":
                price, _, _ = get_stock_data(ticker)
                ratio, eff_date, is_expired = analyze_split_data(main_text)
                
                # Quality Gate: Must have Price & Ratio
                if price > 0 and ratio > 0 and not is_expired:
                    est_value = price * ratio
                    profit = est_value - price
                    
                    msg = (
                        f"🚨 LIVE RSA FOUND: {ticker}\n"
                        f"-------------------------\n"
                        f"PROFIT: ${profit:.2f} per share\n"
                        f"-------------------------\n"
                        f"Price: ${price:.2f}\n"
                        f"Split: 1-for-{ratio}\n"
                        f"Effective: {eff_date}\n"
                        f"Link: {filing.url}"
                    )
                    
                    print(f">>> SENDING ALERT FOR {ticker} <<<")
                    send_telegram_msg(msg)
                    save_seen_filing(filing.accession_number)

        except Exception as e:
            pass

    print(f"Run Complete. Scanned {count_checked} new files.")

if __name__ == "__main__":
    run_rsa_sniper()
