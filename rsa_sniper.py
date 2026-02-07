import os
import requests
import re
import yfinance as yf
from datetime import datetime
from edgar import *
from dateutil import parser 

set_identity("Kevin Anderson kevinand83@gmail.com")
DB_FILE = "seen_filings.txt"

# --- CONFIGURATION ---
FORCE_TEST_TICKER = os.environ.get('TEST_TICKER')
if FORCE_TEST_TICKER:
    FORCE_TEST_TICKER = FORCE_TEST_TICKER.strip().upper()
    if FORCE_TEST_TICKER == "": FORCE_TEST_TICKER = None

SCAN_INPUT = os.environ.get('SCAN_MODE')
IS_DEEP_SCAN = False
if SCAN_INPUT and "Deep" in SCAN_INPUT:
    IS_DEEP_SCAN = True

if FORCE_TEST_TICKER:
    SCAN_DEPTH = 10000
    print(f"--- MODE: SURGICAL TEST ({FORCE_TEST_TICKER}) ---")
elif IS_DEEP_SCAN:
    SCAN_DEPTH = 10000
    print(f"--- MODE: DEEP HISTORY (Last 30 Days) ---")
else:
    SCAN_DEPTH = 500
    print(f"--- MODE: LIVE SENTRY (Last 24 Hours) ---")

def load_seen_filings():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return set(line.strip() for line in f)
    return set()

def save_seen_filing(accession_number):
    with open(DB_FILE, "a") as f:
        f.write(f"{accession_number}\n")

def get_stock_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        try: price = stock.fast_info.last_price
        except: price = stock.info.get('currentPrice', 0.0)
        
        if price is None or price == 0:
            price = stock.info.get('previousClose', 0.0)
            
        try:
            shares = stock.info.get('sharesOutstanding', 0)
            mcap = stock.info.get('marketCap', 0)
        except:
            shares = 0; mcap = 0
            
        if mcap > 1000000: mcap_str = f"${mcap/1000000:.2f}M"
        else: mcap_str = f"${mcap}"
        if shares > 1000000: shares_str = f"{shares/1000000:.2f}M"
        else: shares_str = str(shares)
        return float(price), shares_str, mcap_str
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
            else:
                is_expired = False
        except:
            pass
    return ratio, date_str, is_expired

def check_text_for_gold(text):
    if not text: return False, False
    clean_text = re.sub(r'\s+', ' ', text).lower()
    
    pos_patterns = [r"round(ed|ing)? up", r"next whole share", r"nearest whole share", r"upwardly adjusted"]
    has_pos = any(re.search(p, clean_text) for p in pos_patterns)

    neg_patterns = [r"cash in lieu", r"cash payment", r"rounded down"]
    has_neg = any(re.search(p, clean_text) for p in neg_patterns)

    return has_pos, has_neg

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
    try:
        filings = get_filings(form=["8-K", "6-K"]).latest(SCAN_DEPTH)
        print(f"SUCCESS: Downloaded {len(filings)} filings.")
    except Exception as e:
        print(f"SEC ERROR: {e}")
        return

    seen_filings = load_seen_filings()
    count_checked = 0

    for filing in filings:
        # 1. TICKER & NAME REPAIR
        try:
            ticker = filing.ticker
            company_lower = str(filing.company).lower()
            
            # REPAIR MISSING TICKERS
            if not ticker or ticker == "UNKNOWN":
                if "noodles" in company_lower: ticker = "NDLS"
                elif "edible garden" in company_lower: ticker = "EDBL"
                elif "utime" in company_lower: ticker = "WTO"
                elif "agape" in company_lower: ticker = "ATPC"
                elif "sphere 3d" in company_lower: ticker = "ANY"
                else: ticker = "UNKNOWN"
            
            ticker = str(ticker).upper()
        except:
            ticker = "UNKNOWN"

        # 2. FILTERING
        # A. Test Mode
        if FORCE_TEST_TICKER and ticker != FORCE_TEST_TICKER: continue
        
        # B. Live Mode (Skip Memory & Unknowns)
        if not FORCE_TEST_TICKER and not IS_DEEP_SCAN:
            if ticker == "UNKNOWN": continue
            if filing.accession_number in seen_filings: continue

        # C. Deep Scan (CRITICAL CHANGE: DO NOT SKIP UNKNOWNS if they are Name Matches)
        # If it's still UNKNOWN after the repair step above, THEN we skip it.
        # But if we fixed it to "ATPC", we KEEP it.
        if IS_DEEP_SCAN and ticker == "UNKNOWN": 
            continue

        count_checked += 1
        if count_checked % 100 == 0: print(f"Scanning... Checked {count_checked} docs")

        try:
            main_text = filing.text()
            if not main_text: continue
            has_pos, has_neg = check_text_for_gold(main_text)
            
            if not has_pos and not has_neg:
                for attachment in filing.attachments:
                    try:
                        att_text = attachment.text()
                        p, n = check_text_for_gold(att_text)
                        if p: 
                            has_pos = True
                            main_text = att_text 
                        if n: has_neg = True
                        if has_pos or has_neg: break 
                    except:
                        continue

            if has_pos and not has_neg:
                price, shares, mcap = get_stock_data(ticker)
                ratio, eff_date, is_expired = analyze_split_data(main_text)
                found_at = datetime.now().strftime("%I:%M %p")
                
                if is_expired:
                    header = "⛔ EXPIRED"
                    status = "SPLIT DONE"
                elif ratio > 0 and price > 0:
                    header = "🚨 RSA OPPORTUNITY"
                    est_value = price * ratio
                    profit = est_value - price
                    status = f"PROFIT: ${profit:.2f}"
                else:
                    header = "⚠️ POTENTIAL RSA"
                    status = "Check Math"

                ratio_display = f"1-for-{ratio}" if ratio > 0 else "Unknown"

                msg = (
                    f"{header}: {ticker}\n"
                    f"-------------------------\n"
                    f"STATUS: {status}\n"
                    f"-------------------------\n"
                    f"Price: ${price:.2f}\n"
                    f"Split: {ratio_display}\n"
                    f"Effective: {eff_date}\n"
                    f"-------------------------\n"
                    f"Found: {found_at} ET\n"
                    f"Link: {filing.url}"
                )
                
                print(f">>> SENDING ALERT FOR {ticker} <<<")
                send_telegram_msg(msg)
                
                if not IS_DEEP_SCAN and not FORCE_TEST_TICKER:
                    save_seen_filing(filing.accession_number)

        except Exception as e:
            pass

    print(f"Run Complete. Scanned {count_checked} relevant files.")

if __name__ == "__main__":
    run_rsa_sniper()
