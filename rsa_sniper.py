import os
import requests
import re
import yfinance as yf
from datetime import datetime
from edgar import *
from dateutil import parser 

set_identity("Kevin Anderson kevinand83@gmail.com")
DB_FILE = "seen_filings.txt"

# --- KNOWN TARGETS MAP ---
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

if FORCE_TEST_TICKER:
    SCAN_DEPTH = 10000
    print(f"--- MODE: SURGICAL TEST ({FORCE_TEST_TICKER}) ---")
elif IS_DEEP_SCAN:
    SCAN_DEPTH = 3000
    print(f"--- MODE: DEEP HISTORY (Last 3000 Files) ---")
else:
    SCAN_DEPTH = 500
    print(f"--- MODE: LIVE SNIPER (Last 500 Files) ---")

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
        except:
            pass
    return ratio, date_str, is_expired

def check_gold_status(text):
    """
    BALANCED FILTER:
    Catches ALL variations of 'Round Up'.
    Kills ALL variations of 'Cash'.
    """
    if not text: return "NONE"
    clean_text = re.sub(r'\s+', ' ', text).lower()

    # 1. KILLER PHRASES (If these exist, it's trash)
    bad_patterns = [
        r"cash (payment )?in lieu", 
        r"paid in cash", 
        r"cash for fractional",
        r"rounded down"
    ]
    if any(re.search(p, clean_text) for p in bad_patterns):
        return "BAD"

    # 2. GOLD PHRASES (Expanded List)
    good_patterns = [
        r"round(ed|ing)? up",
        r"whole share",               # Catch "receive a whole share"
        r"upward adjustment",         # Catch "upward adjustment"
        r"nearest whole number",      # Catch "nearest whole number"
        r"fractional shares will be issued", # Rare but good
        r"no fractional shares.*issued", # Often implies rounding if not cash
        r"rounded to the nearest"     # Often means rounding up for 0.5+
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
            
            # Use the Map
            company_lower = str(filing.company).lower()
            for name_key, ticker_val in TARGET_MAP.items():
                if name_key in company_lower:
                    ticker = ticker_val
                    break
            
            ticker = str(ticker).upper()
        except:
            pass

        # 2. FILTERING
        if FORCE_TEST_TICKER and ticker != FORCE_TEST_TICKER: continue
        if not FORCE_TEST_TICKER and not IS_DEEP_SCAN:
            if filing.accession_number in seen_filings: continue

        count_checked += 1
        if count_checked % 100 == 0: print(f"Scanning... Checked {count_checked} docs")

        try:
            main_text = filing.text()
            if not main_text: continue
            
            # --- STRICT BUT SMART FILTERING ---
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
            
            # --- ALERT ---
            if status == "GUARANTEED":
                price, shares, mcap = get_stock_data(ticker)
                ratio, eff_date, is_expired = analyze_split_data(main_text)
                found_at = datetime.now().strftime("%I:%M %p")
                
                # STATUS LOGIC
                if is_expired:
                    header = "⛔ EXPIRED"
                    calc = "Split Already Happened"
                elif ratio > 0 and price > 0:
                    header = "🚨 GUARANTEED ROUND UP"
                    est_value = price * ratio
                    profit = est_value - price
                    calc = f"PROFIT: ${profit:.2f} per share"
                else:
                    header = "⚠️ ROUND UP FOUND"
                    calc = "Check Price/Ratio Manually"

                ratio_display = f"1-for-{ratio}" if ratio > 0 else "Unknown"
                
                # LINK FOR UNKNOWNS
                display_name = ticker
                if ticker == "UNKNOWN":
                    display_name = f"UNK: {filing.company}"
                
                if price == 0 or ticker == "UNKNOWN":
                    search_query = f"{filing.company} stock price"
                    search_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
                    price_line = f"Price: UNKNOWN ([Click to Search]({search_url}))"
                else:
                    price_line = f"Price: ${price:.2f}"

                msg = (
                    f"{header}: {display_name}\n"
                    f"-------------------------\n"
                    f"STATUS: {calc}\n"
                    f"-------------------------\n"
                    f"{price_line}\n"
                    f"Split: {ratio_display}\n"
                    f"Effective: {eff_date}\n"
                    f"-------------------------\n"
                    f"Link: {filing.url}"
                )
                
                print(f">>> GOLD FOUND: {display_name} <<<")
                send_telegram_msg(msg)
                
                if not IS_DEEP_SCAN and not FORCE_TEST_TICKER:
                    save_seen_filing(filing.accession_number)

        except Exception as e:
            pass

    print(f"Run Complete. Scanned {count_checked} files.")

if __name__ == "__main__":
    run_rsa_sniper()
