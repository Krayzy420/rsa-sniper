import os
import requests
import re
import yfinance as yf
from datetime import datetime
from edgar import *

set_identity("Kevin Anderson kevinand83@gmail.com")

DB_FILE = "seen_filings.txt"

# --- INPUTS ---
FORCE_TEST_TICKER = os.environ.get('TEST_TICKER')
if FORCE_TEST_TICKER == "": FORCE_TEST_TICKER = None

SCAN_INPUT = os.environ.get('SCAN_MODE')
IS_DEEP_SCAN = False
if SCAN_INPUT and "Deep" in SCAN_INPUT: IS_DEEP_SCAN = True

def load_seen_filings():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return set(line.strip() for line in f)
    return set()

def save_seen_filing(accession_number):
    with open(DB_FILE, "a") as f:
        f.write(f"{accession_number}\n")

# --- INTELLIGENCE ENGINE ---
def extract_split_details(text):
    """
    Hunts for:
    1. Split Ratio (e.g., "1-for-10")
    2. Effective Date (e.g., "effective August 25")
    """
    clean_text = re.sub(r'\s+', ' ', text).lower()
    
    # 1. FIND RATIO
    # Patterns: "1-for-10", "one-for-ten", "1:10"
    ratio = 0
    ratio_match = re.search(r'1-for-([0-9]+)', clean_text)
    if not ratio_match:
        ratio_match = re.search(r'one-for-([a-z]+)', clean_text)
        # (Simple text-to-number map could go here, keeping it simple for now)
    
    if ratio_match:
        try:
            ratio = int(ratio_match.group(1))
        except:
            ratio = 0 # Failed to parse
            
    # 2. FIND DATE
    # Look for "effective [Month] [Day]"
    date_str = "Check Filing"
    date_match = re.search(r'effective (as of )?([a-z]+ [0-9]{1,2},? [0-9]{4})', clean_text)
    if date_match:
        date_str = date_match.group(2)
        
    return ratio, date_str

def get_stock_data(ticker):
    if ticker == "UNKNOWN": return 0.0, "N/A", "N/A"
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
        
        # Format for readability
        if mcap > 1000000: mcap_str = f"${mcap/1000000:.2f}M"
        else: mcap_str = f"${mcap}"
        
        if shares > 1000000: shares_str = f"{shares/1000000:.2f}M"
        else: shares_str = str(shares)

        return price, shares_str, mcap_str
    except:
        return 0.0, "N/A", "N/A"

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
    
    pos_patterns = [r"round(ed|ing)? up", r"next whole share", r"nearest whole share", r"upwardly adjusted"]
    has_pos = any(re.search(p, clean_text) for p in pos_patterns)

    neg_patterns = [r"cash in lieu", r"cash payment", r"rounded down"]
    has_neg = any(re.search(p, clean_text) for p in neg_patterns)

    return has_pos, has_neg

def run_rsa_sniper():
    # --- MODE SETUP ---
    scan_depth = 500 # Default Live Mode
    if FORCE_TEST_TICKER:
        scan_depth = 10000
        print(f"--- TEST MODE: Searching for {FORCE_TEST_TICKER} ---")
    elif IS_DEEP_SCAN:
        scan_depth = 10000
        print(f"--- DEEP SCAN MODE: Searching Last 30 Days ---")
    else:
        print(f"--- LIVE MODE: Guarding Last 24 Hours ---")

    print(f"Connecting to SEC...")
    try:
        filings = get_filings(form=["8-K", "6-K"]).latest(scan_depth)
        print(f"SUCCESS: Downloaded list of {len(filings)} filings.")
    except Exception as e:
        print(f"SEC ERROR: {e}")
        return

    seen_filings = load_seen_filings()
    count_checked = 0
    found_at = datetime.now().strftime("%I:%M %p")

    for filing in filings:
        # TICKER REPAIR
        try:
            ticker = filing.ticker
            company_lower = filing.company.lower()
            if not ticker:
                if "noodles" in company_lower: ticker = "NDLS"
                elif "edible garden" in company_lower: ticker = "EDBL"
                elif "utime" in company_lower: ticker = "WTO"
                elif "agape" in company_lower: ticker = "ATPC"
                elif "sphere 3d" in company_lower: ticker = "ANY"
                else: ticker = "UNKNOWN"
        except:
            ticker = "UNKNOWN"

        # GATES
        if FORCE_TEST_TICKER and ticker != FORCE_TEST_TICKER: continue
        if not FORCE_TEST_TICKER and filing.accession_number in seen_filings: continue
        if ticker == "UNKNOWN": continue # Skip junk

        count_checked += 1
        if count_checked % 50 == 0: print(f"Scanning {count_checked}...")

        try:
            # 1. READ TEXT
            main_text = filing.text()
            if not main_text: continue
            
            # 2. CHECK FOR ROUND UP
            has_pos, has_neg = check_text_for_gold(main_text)
            
            # If not in main text, check attachments
            if not has_pos and not has_neg:
                for attachment in filing.attachments:
                    try:
                        att_text = attachment.text()
                        p, n = check_text_for_gold(att_text)
                        if p: 
                            has_pos = True
                            # If we found it in attachment, use this text for details
                            main_text = att_text 
                        if n: has_neg = True
                        if has_pos or has_neg: break 
                    except:
                        continue

            # 3. ANALYZE & ALERT
            if has_pos and not has_neg:
                # Get Finance Data
                price, shares, mcap = get_stock_data(ticker)
                
                # Get Intelligence (Ratio & Date)
                ratio, effective_date = extract_split_details(main_text)
                
                # Calculate Profit (The Holy Grail)
                profit_msg = "Calc Failed"
                if ratio > 0 and price > 0:
                    # Logic: You buy 1 share for $Price.
                    # It rounds up to 1 post-split share worth ($Price * Ratio).
                    # Profit = (Price * Ratio) - Price
                    est_value = price * ratio
                    profit = est_value - price
                    profit_msg = f"${profit:.2f} per share"
                    ratio_msg = f"1-for-{ratio}"
                else:
                    ratio_msg = "Check Filing"
                    profit_msg = "Unknown"

                # BUILD THE ALERT
                msg = (
                    f"🚨 RSA GOLD FOUND: {ticker} 🚨\n"
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
                
                if not FORCE_TEST_TICKER:
                    save_seen_filing(filing.accession_number)

        except Exception as e:
            pass

    print(f"Run Complete. Checked {count_checked} new filings.")

if __name__ == "__main__":
    run_rsa_sniper()
