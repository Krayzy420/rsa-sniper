import os
import requests
import re
import yfinance as yf
from datetime import datetime
from edgar import *
from dateutil import parser 

set_identity("Kevin Anderson kevinand83@gmail.com")
DB_FILE = "seen_filings.txt"

# --- TARGET MAP ---
TARGET_MAP = {
    "agape": "ATPC",
    "utime": "WTO",
    "sphere 3d": "ANY",
    "edible garden": "EDBL",
    "noodles": "NDLS",
    "aspirema": "ASPI"
}

# --- CONFIGURATION ---
FORCE_TEST_TICKER = os.environ.get('TEST_TICKER')
if FORCE_TEST_TICKER:
    FORCE_TEST_TICKER = FORCE_TEST_TICKER.strip().upper()
    if FORCE_TEST_TICKER == "": FORCE_TEST_TICKER = None

SCAN_INPUT = os.environ.get('SCAN_MODE')
IS_DEEP_SCAN = False
if SCAN_INPUT and "Deep" in SCAN_INPUT:
    IS_DEEP_SCAN = True

# --- MAX HORSEPOWER SETTINGS ---
if FORCE_TEST_TICKER:
    # 1. SURGICAL STRIKE (Instant)
    SCAN_DEPTH = 10 
    print(f"--- MODE: SURGICAL STRIKE ({FORCE_TEST_TICKER}) ---")
elif IS_DEEP_SCAN:
    # 2. MAX DEEP SCAN (Manual Run)
    # 2000 files @ 40 files/min = ~50 minute run time.
    # This is the "Fullest of the Free" before getting annoying.
    SCAN_DEPTH = 2000
    print(f"--- MODE: MAX DEEP SCAN (Last 2000 Files) ---")
else:
    # 3. MAX LIVE SCAN (Auto Run)
    # 200 files @ 40 files/min = 5 minute run time.
    # Fits perfectly in the 5-minute schedule.
    SCAN_DEPTH = 200
    print(f"--- MODE: LIVE SENTRY (Last 200 Files) ---")

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

    # KILLER PHRASES
    bad_patterns = [r"cash (payment )?in lieu", r"paid in cash", r"rounded down"]
    if any(re.search(p, clean_text) for p in bad_patterns):
        return "BAD"

    # GOLD PHRASES
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
    print(f"Connecting to SEC...")
    
    # --- INTELLIGENT DOWNLOADING ---
    if FORCE_TEST_TICKER:
        try:
            filings = get_filings(ticker=FORCE_TEST_TICKER).latest(SCAN_DEPTH)
            print(f"SUCCESS: Downloaded {len(filings)} filings for {FORCE_TEST_TICKER}.")
        except Exception as e:
            print(f"Error finding ticker {FORCE_TEST_TICKER}: {e}")
            return
    else:
        try:
            filings = get_filings(form=["8-K", "6-K"]).latest(SCAN_DEPTH)
            print(f"SUCCESS: Downloaded {len(filings)} filings.")
        except Exception as e:
            print(f"SEC Error: {e}")
            return

    seen_filings = load_seen_filings()
    count_checked = 0

    for filing in filings:
        # IDENTIFY
        ticker = "UNKNOWN"
        try:
            if filing.ticker: ticker = filing.ticker
            company_lower = str(filing.company).lower()
            for name_key, ticker_val in TARGET_MAP.items():
                if name_key in company_lower:
                    ticker = ticker_val
                    break
            ticker = str(ticker).upper()
        except:
            pass

        # FILTER SEEN (Only in Auto Mode. Deep Scan shows history.)
        if not FORCE_TEST_TICKER and not IS_DEEP_SCAN:
            if filing.accession_number in seen_filings: continue

        count_checked += 1
        # PRINT UPDATE EVERY 10 DOCS (So you know it's moving)
        if count_checked % 10 == 0: 
            print(f"Scanning... Checked {count_checked} docs")

        try:
            main_text = filing.text()
            if not main_text: continue
            
            status = check_gold_status(main_text)
            
            if status == "NONE":
                for attachment in filing.attachments:
                    try:
                        att_text = attachment.text()
                        if check_gold_status(att_text) == "GUARANTEED": 
                            status = "GUARANTEED"
                            main_text = att_text
                            break
                    except: continue
            
            if status == "GUARANTEED":
                price, _, _ = get_stock_data(ticker)
                ratio, eff_date, is_expired = analyze_split_data(main_text)
                
                show_alert = False
                
                # DEEP SCAN / TEST: Show EVERYTHING (History)
                if IS_DEEP_SCAN or FORCE_TEST_TICKER:
                    show_alert = True
                    if is_expired:
                         header = "⛔ EXPIRED (HISTORY)"
                         calc = "Proof of Life"
                    else:
                         header = "🚨 ACTIVE RSA"
                         if price > 0 and ratio > 0:
                             calc = f"PROFIT: ${(price*ratio)-price:.2f}"
                         else:
                             calc = "Check Math"

                # LIVE MODE: Show ONLY Valid Profitable Deals
                elif not is_expired and price > 0 and ratio > 0:
                    show_alert = True
                    header = "🚨 LIVE RSA FOUND"
                    calc = f"PROFIT: ${(price*ratio)-price:.2f}"

                if show_alert:
                    ratio_display = f"1-for-{ratio}"
                    if price == 0: price_line = "Price: UNKNOWN (Google it)"
                    else: price_line = f"Price: ${price:.2f}"

                    msg = (
                        f"{header}: {ticker}\n"
                        f"-------------------------\n"
                        f"{calc}\n"
                        f"-------------------------\n"
                        f"{price_line}\n"
                        f"Split: {ratio_display}\n"
                        f"Effective: {eff_date}\n"
                        f"Link: {filing.url}"
                    )
                    print(f">>> HIT: {ticker} <<<")
                    send_telegram_msg(msg)
                    
                    if not FORCE_TEST_TICKER and not IS_DEEP_SCAN:
                        save_seen_filing(filing.accession_number)

        except Exception as e:
            pass

    print(f"Run Complete. Scanned {count_checked} files.")

if __name__ == "__main__":
    run_rsa_sniper()
